# Copyright(C) 2012 Romain Bignon
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

import json
import re
from io import BytesIO
from decimal import Decimal
from datetime import date, datetime

from dateutil.tz import tz
from dateutil.parser import parse as parse_date
from PIL import Image, ImageFilter

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.html import Attr, Link
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    CleanDecimal, CleanText, Coalesce,
    Currency, Date, Env, Eval, Field,
    Format, Lower, MapIn, Regexp,
)
from woob.browser.pages import (
    HTMLPage, JsonPage, LoggedPage,
    RawPage, XMLPage,
)
from woob.capabilities.bank import (
    Account, Loan, AccountOwnership,
    AccountOwnerType,
)
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.base import NotAvailable, empty
from woob.exceptions import (
    AppValidationCancelled, BrowserIncorrectPassword,
    BrowserPasswordExpired, BrowserUserBanned,
)
from woob.tools.capabilities.bank.iban import rib2iban
from woob.tools.capabilities.bank.investments import is_isin_valid, IsinCode, IsinType
from woob.tools.capabilities.bank.transactions import FrenchTransaction
from woob.tools.captcha.virtkeyboard import SplitKeyboard


def float_to_decimal(f):
    return Decimal(str(f))


class LoginPage(HTMLPage):
    def get_main_js_file_url(self):
        return Attr(
            '//script[contains(@src, "main-")] | //script[contains(@src, "main.")]', 'src'
        )(self.doc)


class HomePage(LoginPage):
    pass


class ConfigPage(JsonPage):
    def get_continue_url(self, cdetab, user_type):
        continue_url = self.doc['continueUrls']['dei'].get(cdetab)
        if not continue_url:
            raise BrowserIncorrectPassword()

        return continue_url[user_type]


class JsFilePage(RawPage):
    def get_first_client_id(self):
        # Needed for pre-login
        return Regexp(pattern=r'anonymous:{clientId:\"(.*?)\"').filter(self.text)

    def get_second_client_id(self):
        # Needed for login initialization
        return Regexp(pattern=r'{authenticated:{clientId:"([^"]+)"').filter(self.text)

    def get_third_client_id(self):
        # Needed for login finalization
        return Regexp(pattern=r'pasConfig:{.*:.*,clientId:\"(.*?)\"').filter(self.text)

    def get_third_client_id_for_cenet(self):
        return Regexp(pattern=r'client_id:"(.*?)"').filter(self.text)

    def get_loans_client_id(self):
        return Regexp(pattern=r'bapi:{clientId:\"(.*?)\"').filter(self.text)

    def get_nonce(self):
        return Regexp(pattern=r'\("nonce","([a-z0-9]+)"\)').filter(self.text)

    def get_snid(self, bank):
        snid_dict = Regexp(pattern=r'const e=(\{BCP.*?\})\},', default=NotAvailable).filter(self.text)
        assert snid_dict, 'Could not find SNIDs in main JS, check if it has been updated'

        # dict is formatted like a JS dict, keys aren't quoted, must be
        # fixed for python to handle it correctly.
        json_snid_dict = json.loads(re.sub('([A-Z]+)', '"\\1"', snid_dict))

        return json_snid_dict[bank]


class AuthorizePage(HTMLPage):
    def send_form(self):
        form = self.get_form(id='submitMe')
        # For caissedepargne, referer can be the BASEURL or a quite long URL with a lot of params.
        # Children modules check for headers length and will answer with a HTTP 430 response if
        # the referer is too long.
        form.submit(headers={'Referer': self.browser.BASEURL})


class AuthenticationMethodPage(JsonPage):
    IS_SCA_CODE = {
        None: False,  # When the auth is finished, there is no more SCA
        '101': False,  # Caisse d'Épargne, Banque Populaire - SCA has been validated
        '103': False,  # Palatine, Banque Populaire - SCA has been validated
        '105': False,  # Seen for Caisse d'Épargne, Banque Populaire
        '245': False,  # Caisse d'Épargne
        '247': True,  # Caisse d'Épargne, Crédit Coopératif, linked to EMV
        '261': True,  # Caisse d'Épargne, Palatine
        '263': True,  # Banque Populaire
        '265': True,  # Caisse d'Épargne, SCA with SMS OTP
        '267': True,  # Caisse d'Épargne, Crédit Coopératif, linked to EMV
        '291': True,  # Seen for CLOUDCARD and SMS on Banque Populaire
        '281': True,  # Seen for CLOUDCARD on Caisse d'Épargne
    }

    def get_validation_id(self):
        return Dict('id', default=NotAvailable)(self.doc)

    def get_wrong_pre_login_status(self):
        if (
            not Dict('step/validationUnits', default=None)(self.doc)
            and not Dict('validationUnits', default=None)(self.doc)
        ):
            # 'validationUnits' informs about auth method
            # not having any is faulty for the connection
            status = self.doc['response']['status']
            assert status in ('AUTHENTICATION_FAILED',), (
                'Unhandled status when checking if authentication method is informed: %s' % status
            )
            return status

    def get_saml_response(self):
        return self.doc['response'].get('saml2_post', {}).get('samlResponse', '')

    @property
    def validation_units(self):
        validation_unit = self._safe_validation_units()
        if validation_unit is None:
            raise AssertionError('A validation unit exist but it has no required operation.')
        return validation_unit

    @property
    def has_validation_unit(self):
        return self._safe_validation_units() is not None

    def _safe_validation_units(self):
        units = Coalesce(
            Dict('step/validationUnits', default=None),
            Dict('validationUnits', default=None),
            default=None
        )(self.doc)
        if units is not None and len(units) > 0:
            return units[0]

    @property
    def validation_unit_id(self):
        if len(self.validation_units) != 1:
            raise AssertionError('There should be exactly one authentication operation required.')
        # The data we are looking for is in a dict with a random uuid key.
        return next(iter(self.validation_units))

    def get_authentication_method_info(self):
        # The data we are looking for is in a dict with a random uuid key.
        return self.validation_units[self.validation_unit_id][0]

    @property
    def phase(self):
        return Coalesce(
            Dict('step/phase', default=None),
            Dict('phase', default=None),
            default={}
        )(self.doc)

    def is_other_authentication_method(self):
        is_other_authentication_method = self.phase.get("fallbackFactorAvailable")
        if is_other_authentication_method:
            # Need a logger to try to better handle that process.
            self.logger.warning('Found a fallbackFactorAvailable, try to fall back to other auth methods.')
        return is_other_authentication_method

    @property
    def security_level(self):
        return self.phase.get("securityLevel")

    def is_sca_expected(self):
        """
        If the security level code is known, returns
        True or False using the IS_SCA_CODE mapping.

        Else, returns 'unknown'.
        """
        # TODO: Move this to Browser when we make a common login
        # for caissedepargne and banquepopulaire.
        return self.IS_SCA_CODE.get(self.security_level, 'unknown')

    def get_authentication_method_type(self):
        return self.get_authentication_method_info()['type']

    def login_errors(self, error):
        # AUTHENTICATION_LOCKED is a BrowserIncorrectPassword because there is a key
        # 'unlockingDate', in the json, that tells when the account will be unlocked.
        # So it does not require any action from the user and is automatic.
        if error == 'AUTHENTICATION_LOCKED':
            message = "L'accès à votre espace a été bloqué temporairement suite à plusieurs essais infructueux."
            if 'response' in self.doc and self.doc['response'].get('unlockingDate'):
                unlocking_date = parse_date(
                    self.doc['response']['unlockingDate']  # parse datetime, tz aware, on UTC
                ).astimezone(tz.tzlocal())  # convert to our timezone
                message = ' '.join([message, 'Vous pouvez réessayer à partir du %s' % unlocking_date])
            raise BrowserUserBanned(message)
        if error in ('FAILED_AUTHENTICATION', ):
            raise BrowserIncorrectPassword('Les identifiants renseignés sont incorrects.')
        if error in ('AUTHENTICATION_FAILED', ):
            # Depending on the authentication mode, this can have different meanings
            # otp: Too much otp asked in the same time
            # emv (falling back on the password):
            #   """L'accès à votre espace bancaire est impossible en raison de données manquantes.
            #   Merci de bien vouloir vous rapprocher de votre conseiller."""
            # Either way, the user is banned and can't access his bank account
            raise BrowserUserBanned(
                "L'accès à votre espace est impossible. Merci de réessayer ultérieurement ou de contacter votre conseiller"
            )
        if error in ('ENROLLMENT', ):
            raise BrowserPasswordExpired()
        if error == 'AUTHENTICATION_CANCELED':
            raise AppValidationCancelled()
        if error:
            raise AssertionError(f'Unhandled login error: {error}')

    def check_errors(self, feature):
        if 'response' in self.doc:
            result = self.doc['response']['status']
        elif 'step' in self.doc:
            # Can have error at first authentication request,
            # error will be handle in `if` case.
            # If there is no error, it will retrive 'AUTHENTICATION' as result value.
            result = self.doc['step']['phase']['state']
        elif 'phase' in self.doc and self.get_authentication_method_type() in (
            'PASSWORD_ENROLL', 'PASSWORD', 'SMS', 'EMV', 'CLOUDCARD',
        ):
            result = self.doc['phase']['state']
            # A failed authentication (e.g. wrongpass) could match the self.doc['phase']['state'] structure
            # of the JSON object returned is case of a fallback authentication
            # So we could mistake a failed authentication with an authentication fallback step
            # Double checking with the presence of previousResult key
            previous_result = Dict('phase/previousResult', default=None)(self.doc)
            if previous_result:
                result = previous_result
        else:
            raise AssertionError('Unexpected response during %s authentication' % feature)

        if result in ('AUTHENTICATION', 'AUTHENTICATION_SUCCESS'):
            return

        FEATURES_ERRORS = {
            'login': self.login_errors,
        }
        FEATURES_ERRORS[feature](error=result)

        raise AssertionError('Error during %s authentication is not handled yet: %s' % (feature, result))


class SAMLRequestFailure(HTMLPage):
    def is_unavailable(self):
        return 'Merci de bien vouloir nous en excuser' in CleanText('//div[@id="technicalError"]')(self.doc)


class AuthenticationStepPage(AuthenticationMethodPage):
    def get_redirect_data(self):
        # In case of wrongpass the response key does not exist
        # So it needs a default value
        return Dict('response/saml2_post', default=NotAvailable)(self.doc)


class VkImagePage(JsonPage):
    def get_all_images_data(self):
        return self.doc


class ValidationPageOption(LoggedPage, HTMLPage):
    pass


class TokenPage(JsonPage):
    def get_access_token(self):
        return Dict('access_token')(self.doc)


class LoginApi(JsonPage):
    user_types = {
        '1': 'part',
        '2': 'pro',
        '3': 'pp',
        '4': 'sp',  # Don't know what this is, linked '4' to it because 'sp' is the only type of connection left
        '5': 'ent',
    }

    def get_cdetab(self):
        return Dict('characteristics/bankId')(self.doc)

    def is_auth_type_available(self, auth_type_choice):
        user_types = [key for key, value in self.user_types.items() if value == auth_type_choice]
        available_auths = [auth.get('code').lower() for auth in self.doc['characteristics']['subscribeTypeItems']]

        for user_type in user_types:
            if user_type in available_auths:
                return True
        return False

    def get_connection_type(self):
        user_subscriptions = []
        for sub in self.doc['characteristics']['subscribeTypeItems']:
            # MapIn because it can be "Abonnement Particulier" for example
            user_subscriptions.append(MapIn(self.doc, self.user_types).filter(sub['code'].lower()))

        if len(user_subscriptions) == 2:
            # Multi spaces
            if 'part' in user_subscriptions:
                if not self.browser.nuser:
                    return 'part'
                else:
                    # If user gives nuser we must go to ent/pro/pp website
                    return [sub for sub in user_subscriptions if sub != 'part'][0]
            else:
                # Never seen this case yet
                # All these spaces need nuser
                # But we don't know which one to go
                raise AssertionError('There are 2 spaces without part')

        elif len(user_subscriptions) > 2:
            raise AssertionError('There are 3 spaces, need to check how to choose the good one')

        return user_subscriptions[0]


class LoginTokensPage(LoggedPage, JsonPage):
    def get_access_token(self):
        return Dict('parameters/access_token')(self.doc)

    def get_id_token(self):
        return Dict('parameters/id_token')(self.doc)


class CaissedepargneNewKeyboard(SplitKeyboard):
    char_to_hash = {
        '0': '66ec79b200706e7f9c14f2b6d35dbb05',
        '1': ('529819241cce382b429b4624cb019b56', '0ea8c08e52d992a28aa26043ffc7c044'),
        '2': 'fab68678204198b794ce580015c8637f',
        '3': '3fc5280d17cf057d1c4b58e4f442ceb8',
        '4': (
            'dea8800bdd5fcaee1903a2b097fbdef0', 'e413098a4d69a92d08ccae226cea9267',
            '61f720966ccac6c0f4035fec55f61fe6', '2cbd19a4b01c54b82483f0a7a61c88a1',
        ),
        '5': 'ff1909c3b256e7ab9ed0d4805bdbc450',
        '6': '7b014507ffb92a80f7f0534a3af39eaa',
        '7': '7d598ff47a5607022cab932c6ad7bc5b',
        '8': ('4ed28045e63fa30550f7889a18cdbd81', '88944bdbef2e0a49be9e0c918dd4be64'),
        '9': 'dd6317eadb5a0c68f1938cec21b05ebe',
    }
    codesep = ' '

    def __init__(self, browser, images):
        code_to_filedata = {}
        for img_item in images:
            img_content = browser.location(img_item['uri']).content
            img = Image.open(BytesIO(img_content))
            img = img.filter(ImageFilter.UnsharpMask(
                radius=2,
                percent=150,
                threshold=3,
            ))
            img = img.convert('L', dither=None)

            def threshold(px):
                if px < 20:
                    return 0
                return 255

            img = Image.eval(img, threshold)
            b = BytesIO()
            img.save(b, format='PNG')
            code_to_filedata[img_item['value']] = b.getvalue()
        super(CaissedepargneNewKeyboard, self).__init__(code_to_filedata)


class Transaction(FrenchTransaction):
    PATTERNS = [
        (
            re.compile(r'^CB (?P<text>.*?) FACT (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{2})\b', re.IGNORECASE),
            FrenchTransaction.TYPE_CARD,
        ),
        (re.compile(r'^RET(RAIT)? DAB (?P<dd>\d+)-(?P<mm>\d+)-.*', re.IGNORECASE), FrenchTransaction.TYPE_WITHDRAWAL),
        (
            re.compile(
                r'^RET(RAIT)? DAB (?P<text>.*?) (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{2}) (?P<HH>\d{2})H(?P<MM>\d{2})\b',
                re.IGNORECASE
            ),
            FrenchTransaction.TYPE_WITHDRAWAL,
        ),
        (re.compile(r'^VIR(EMENT)?(\.PERIODIQUE)? (?P<text>.*)', re.IGNORECASE), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r'^PRLV (?P<text>.*)', re.IGNORECASE), FrenchTransaction.TYPE_ORDER),
        (re.compile(r'^CHEQUE.*', re.IGNORECASE), FrenchTransaction.TYPE_CHECK),
        (re.compile(r'^(CONVENTION \d+ )?COTIS(ATION)? (?P<text>.*)', re.IGNORECASE), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^\* ?(?P<text>.*)', re.IGNORECASE), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^REMISE (?P<text>.*)', re.IGNORECASE), FrenchTransaction.TYPE_CHECK),
        (re.compile(r'^Depot Esp (?P<text>.*)', re.IGNORECASE), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r'^(?P<text>.*)( \d+)? QUITTANCE .*', re.IGNORECASE), FrenchTransaction.TYPE_ORDER),
        (re.compile(r'^CB [\d\*]+ TOT DIF .*', re.IGNORECASE), FrenchTransaction.TYPE_CARD_SUMMARY),
        (re.compile(r'^CB [\d\*]+ (?P<text>.*)', re.IGNORECASE), FrenchTransaction.TYPE_CARD),
        (
            re.compile(r'^CB (?P<text>.*?) (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{2})\b', re.IGNORECASE),
            FrenchTransaction.TYPE_CARD,
        ),
        (
            re.compile(r'\*CB (?P<text>.*?) (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{2})\b', re.IGNORECASE),
            FrenchTransaction.TYPE_CARD,
        ),
        (
            re.compile(r'^FAC CB (?P<text>.*?) (?P<dd>\d{2})/(?P<mm>\d{2})\b', re.IGNORECASE),
            FrenchTransaction.TYPE_CARD,
        ),
        (re.compile(r'^\*?CB (?P<text>.*)', re.IGNORECASE), FrenchTransaction.TYPE_CARD),
        # For life insurances and capitalisation contracts
        (re.compile(r'^VERSEMENT', re.IGNORECASE), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r'^Réinvestissement', re.IGNORECASE), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r'^REVALORISATION', re.IGNORECASE), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^ARBITRAGE', re.IGNORECASE), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^RACHAT PARTIEL', re.IGNORECASE), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(?P<text>INTERETS.*)', re.IGNORECASE), FrenchTransaction.TYPE_BANK),
        (
            re.compile(r'^ECH PRET (?P<text>.*) DU (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{2})', re.IGNORECASE),
            FrenchTransaction.TYPE_LOAN_PAYMENT,
        ),
    ]


ACCOUNT_TYPES = {
    'Epargne liquide': Account.TYPE_SAVINGS,
    'Compte Courant': Account.TYPE_CHECKING,
    'COMPTE A VUE': Account.TYPE_CHECKING,
    'COMPTE CHEQUE': Account.TYPE_CHECKING,
    'Mes comptes': Account.TYPE_CHECKING,
    'COMPTE DE DEPOT': Account.TYPE_CHECKING,
    'CPT DEPOT PART.': Account.TYPE_CHECKING,
    'CPT DEPOT PROF.': Account.TYPE_CHECKING,
    'Mon épargne': Account.TYPE_SAVINGS,
    'Mes autres comptes': Account.TYPE_SAVINGS,
    'Compte Epargne et DAT': Account.TYPE_SAVINGS,
    'Plan et Contrat d\'Epargne': Account.TYPE_SAVINGS,
    'COMPTE SUR LIVRET': Account.TYPE_SAVINGS,
    'LIVRET DEV.DURABLE': Account.TYPE_SAVINGS,
    'LDD Solidaire': Account.TYPE_SAVINGS,
    'LDDS': Account.TYPE_SAVINGS,
    'LIVRET A': Account.TYPE_SAVINGS,
    'LIVRET B': Account.TYPE_SAVINGS,  # Savings account specific to Caissedepargne.
    'LIVRET JEUNE': Account.TYPE_SAVINGS,
    'LIVRET GRAND PRIX': Account.TYPE_SAVINGS,
    'LEP': Account.TYPE_SAVINGS,
    'L.EPAR POPULAIRE': Account.TYPE_SAVINGS,
    'LEL': Account.TYPE_SAVINGS,
    'PLAN EPARG. LOGEMENT': Account.TYPE_SAVINGS,
    'L. EPAR LOGEMENT': Account.TYPE_SAVINGS,
    'CPT PARTS SOCIALES': Account.TYPE_MARKET,
    'PEL': Account.TYPE_SAVINGS,
    'PEL 16 2013': Account.TYPE_SAVINGS,
    'PEL 16 2014': Account.TYPE_SAVINGS,
    'PARTS SOCIALES': Account.TYPE_MARKET,
    'Titres': Account.TYPE_MARKET,
    'Compte titres': Account.TYPE_MARKET,
    'Mes crédits immobiliers': Account.TYPE_MORTGAGE,
    'Mes crédits renouvelables': Account.TYPE_REVOLVING_CREDIT,
    'Mes crédits consommation': Account.TYPE_CONSUMER_CREDIT,
    'PEA NUMERAIRE': Account.TYPE_PEA,
    'COMPTE NUMERAIRE PEA': Account.TYPE_PEA,
    'PEA': Account.TYPE_PEA,
    'primo': Account.TYPE_MORTGAGE,
    'equipement': Account.TYPE_LOAN,
    'garanti par l\'état': Account.TYPE_LOAN,
    'credits de tresorerie': Account.TYPE_LOAN,
    'PRET IMMOBILIER': Account.TYPE_LOAN,
    'Crédit renouvelable': Account.TYPE_REVOLVING_CREDIT,
    'MILLEVIE ESSENTIELLE': Account.TYPE_LIFE_INSURANCE,
    'MILLEVIE PREMIUM': Account.TYPE_LIFE_INSURANCE,
    'MILLEVIE INFINIE 2': Account.TYPE_LIFE_INSURANCE,
    'MILLEVIE PER': Account.TYPE_PER,
    'INITIATIVES TRANSMIS': Account.TYPE_LIFE_INSURANCE,
    'CPT TITRE ORD.': Account.TYPE_MARKET,
    'PRET CONSO': Account.TYPE_CONSUMER_CREDIT,
    'NUANCES CAPITALISATI': Account.TYPE_CAPITALISATION,
    'NUANCES 3D': Account.TYPE_LIFE_INSURANCE,
    'NUANCES PLUS': Account.TYPE_LIFE_INSURANCE,
    'MULTIANCE CAP 1818': Account.TYPE_LIFE_INSURANCE,
    'PEL 16': Account.TYPE_SAVINGS,
    'PERP': Account.TYPE_PERP,
    'habitat': Account.TYPE_MORTGAGE,
}

ACCOUNT_OWNER_TYPE = {
    'personnel': AccountOwnerType.PRIVATE,
    'particulier': AccountOwnerType.PRIVATE,
    'professionnel': AccountOwnerType.ORGANIZATION,
}

ACCOUNT_OWNERSHIP_TYPE = {
    'titulaire': AccountOwnership.OWNER,
    'compte individuel': AccountOwnership.OWNER,
    'compte joint': AccountOwnership.CO_OWNER,
    # If you see an attorney case, add it here
}


class AccountItemElement(ItemElement):
    klass = Account

    def condition(self):
        # Skip aggregated accounts from other banks and loans.
        return (
            CleanText(Dict('identity/entityCode'))(self) != 'otherbanks'
            and 'crédit' not in Lower(CleanText(Dict('identity/productFamilyPFM/label')))(self)
            and CleanText(Dict('identity/status/label'))(self) == 'Actif'
        )

    def obj_id(self):
        if Field('type')(self) in (
            Account.TYPE_LOAN,
            Account.TYPE_CONSUMER_CREDIT,
            Account.TYPE_CAPITALISATION,
            Account.TYPE_REVOLVING_CREDIT,
        ):
            return CleanText(Dict('identity/customerReference'))(self)
        return CleanText(Dict('identity/producerContractId'))(self)

    obj_number = CleanText(Dict('identity/customerReference'))

    def obj_label(self):
        if CleanText(Dict('identity/productFamilyPFM/label'))(self) == 'Comptes courants':
            return CleanText(Dict('identity/productLabel'))(self)
        elif CleanText(Dict('identity/productFamilyPFM/label'))(self) == 'Crédits renouvelables':
            return Format(
                '%s %s',
                CleanText(Dict('identity/contractLabel')),
                CleanText(Dict('identity/customerReference')),
            )(self)
        label = CleanText(Dict('identity/contractLabel'))(self)
        if '\x00' in label:
            # Only seen one case where the contractLabel value is
            # something like "\x00\x00\x00\x00\x00...". Value in
            # productLabel is then what is displayed on the website
            # interface.
            return CleanText(Dict('identity/productLabel'))(self)
        return label

    obj_type = MapIn(Field('label'), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)
    obj_balance = CleanDecimal.SI(Dict('identity/balance/value', default=NotAvailable), default=NotAvailable)
    obj_currency = Currency(Dict('identity/balance/currencyCode', default=''))

    def obj_iban(self):
        if Field('type')(self) not in (
            Account.TYPE_CAPITALISATION,
            Account.TYPE_LIFE_INSURANCE,
            Account.TYPE_REVOLVING_CREDIT,
            Account.TYPE_CONSUMER_CREDIT,
            Account.TYPE_LOAN,
            Account.TYPE_PERP,
        ):
            return rib2iban(CleanText(Dict('identity/producerContractId'))(self))
        return NotAvailable

    obj_owner_type = MapIn(
        Lower(CleanText(Dict('identity/relationContext/label'))),
        ACCOUNT_OWNER_TYPE,
    )
    obj_ownership = MapIn(
        Lower(CleanText(Dict('identity/contractLabel'))),
        ACCOUNT_OWNERSHIP_TYPE,
        NotAvailable,
    )

    def obj_coming(self):
        if Field('type')(self) in (
            Account.TYPE_CHECKING,
            Account.TYPE_SAVINGS,
            Account.TYPE_CARD,
        ):
            return CleanDecimal.SI(
                Dict('identity/upcomingTransactionsTotalAmount/value', default=NotAvailable),
                default=NotAvailable,
            )(self)
        return NotAvailable

    def obj__has_card(self):
        return bool(Dict('identity/augmentedCards', default=NotAvailable)(self))

    def obj__is_cash_pea(self):
        # Needed for cash PEA accounts that are found on regular
        # caissedepargne space whereas noncash PEA are on linebourse.
        return 'NUMERAIRE' in Field('label')(self)

    def obj__website_id(self):
        # _website_id is mostly used to get account history or investments.
        if (
            Field('type')(self) in (
                Account.TYPE_REVOLVING_CREDIT,
                Account.TYPE_MARKET,
                Account.TYPE_LIFE_INSURANCE,
                Account.TYPE_CAPITALISATION,
                Account.TYPE_PEA,
            ) and not Field('_is_cash_pea')(self)
        ):
            return Format(
                '%s-%s',
                CleanText(Dict('identity/entityCode')),
                Dict('identity/producerContractId'),  # There are sometimes double spaces that must be used in subsequent requests, don't use CleanText filter here.
            )(self)

        elif Field('type')(self) == Account.TYPE_LOAN:
            return Format(
                '%s-%s',
                CleanText(Dict('identity/entityCode')),
                CleanText(Dict('identity/customerReference')),
            )(self)

        elif Field('type')(self) == Account.TYPE_CONSUMER_CREDIT:
            return Field('number')(self)

        # For at least one pro checking account, contractPfmId is null and
        # ID is formed like the one for revolving credits, markets, etc. There
        # are a few key that are set differently in the JSON of that account
        # but this will have to be compared to more cases to determine upon
        # which rule we can filter this peculiar type of checking account.
        return Coalesce(
            CleanText(Dict('identification/contractPfmId'), default=NotAvailable),
            Format(
                '%s-%s',
                CleanText(Dict('identity/entityCode')),
                Dict('identity/producerContractId'),
            ),
        )(self)


class AccountsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):
        item_xpath = 'items'

        class item(AccountItemElement):
            pass

    @method
    class iter_cards(DictElement):
        def find_elements(self):
            # Cards have no values in common with parent account and are located
            # in a subsection of the parent JSON. Only way to match them is to
            # look for the right parent section and then select the cards subsection.
            for account in Dict('items')(self):
                if Dict('identity/customerReference')(account) == Env('parent_account')(self).number:
                    yield from Dict('identity/augmentedCards')(account)
                    break

        class item(ItemElement):
            klass = Account

            def condition(self):
                # For cases encountered so far, cardStatusType/label "Indéterminé"
                # means that the card is not displayed at all on the website.
                return (
                    CleanText(Dict('cardStatusType/label'))(self) == 'Active'
                    and CleanText(Dict('defferedDebitIndicator'))(self) == 'True'
                )

            # Card ID matching old website card ID can only be found later. If there are several cards,
            # they will all have an ID set at zero (woob default), making store function think we
            # have duplicates. Using ignore_duplicate should be avoided since these are not real
            # duplicates. Setting the value to NotAvailable instead before getting the value later.
            obj_id = NotAvailable

            obj_label = Format(
                '%s %s %s',
                CleanText(Dict('cardProductLabel')),
                CleanText(Dict('cardHolder')),
                CleanText(Dict('primaryAccountNumberMask')),
            )
            obj_type = Account.TYPE_CARD
            obj_balance = CleanDecimal(0)

            obj_currency = Currency(Dict('outstandingCard/currentMonth/amount/currencyCode'))

            def obj_owner_type(self):
                return Env('parent_account')(self).owner_type

            obj_coming = CleanDecimal.SI(Dict('outstandingCard/currentMonth/amount/value'))

            obj_parent = Env('parent_account')

            def obj__website_id(self):
                # Used for history
                return CleanText(Dict('cardPfmId'))(self)

            obj__details_id = CleanText(Dict('cardId/id'))  # Used for account details

    @method
    class iter_loans(DictElement):
        item_xpath = 'items'

        class item(AccountItemElement):
            klass = Loan

            def condition(self):
                # Skip aggregated accounts from other banks and regular accounts.
                return (
                    CleanText(Dict('identity/entityCode'))(self) != 'otherbanks'
                    and 'crédit' in Lower(CleanText(Dict('identity/productFamilyPFM/label')))(self)
                    and CleanText(Dict('identity/status/label'))(self) == 'Actif'
                )


class CardsPage(LoggedPage, JsonPage):
    def fill_cards(self, card):
        # There are many IDs from AccountsPage that we could use
        # but we must get the ID from this specific details page
        # to match old website IDs.
        for _card in self.doc['items']:
            if Dict('identification/cardId')(_card) == card._details_id:
                card.id = Format(
                    '%s_Visa',
                    CleanText(
                        Dict('characteristics/primaryAccountNumberMask'),
                        replace=[(' ', ''), ('•', 'X')],
                    )
                )(_card)
                card.number = CleanText(Dict('characteristics/primaryAccountNumberMask'))(_card)
                card.ownership = MapIn(
                    Lower(CleanText(Dict('cardUser/cardUserType/label'))),
                    ACCOUNT_OWNERSHIP_TYPE,
                    NotAvailable,
                )(_card)


class RevolvingDetailsPage(LoggedPage, JsonPage):
    @method
    class fill_revolving_details(ItemElement):
        item_xpath = 'revolvingCreditSynthesisView'

        obj_total_amount = CleanDecimal.SI(Dict('maximumCreditAllowedAmount/value'))
        obj_available_amount = CleanDecimal.SI(Dict('totalCreditAmount/value'))
        obj_used_amount = CleanDecimal.SI(Dict('outstandingCapitalAmount/value'))
        obj_currency = Currency(Dict('totalCreditAmount/currencyCode'))
        obj_duration = Eval(int, Dict('numberOfRescheduling'))
        obj_rate = CleanDecimal.SI(Dict('tAEG'))


class ConsumerCreditDetailsPage(LoggedPage, JsonPage):
    @method
    class fill_consumer_credit_details(ItemElement):
        item_xpath = 'personalLoanPrdSynthesisView'

        obj_total_amount = CleanDecimal.SI(Dict('folder/requestedAmount/value'))
        obj_rate = CleanDecimal.SI(Dict('folder/tAEG'))
        obj_next_payment_amount = CleanDecimal.SI(Dict('folder/nextMonthlyPaymentAmount/value'))
        obj_next_payment_date = Date(Dict('folder/nextDueDate'), dayfirst=True)
        obj_last_payment_date = Date(Dict('folder/lastDueDate'), dayfirst=True)
        obj_duration = Eval(int, Dict('offer/duration'))
        obj_subscription_date = Date(CleanText(Dict('offer/signatureDate')), dayfirst=True)
        obj_maturity_date = Date(CleanText(Dict('folder/lastDueDate')), dayfirst=True)
        obj_nb_payments_left = Eval(int, Dict('folder/remainingMonthlyPayment'))
        obj_start_repayment_date = Date(Dict('offer/firstDueDate'), dayfirst=True)


class LoanDetailsPage(LoggedPage, JsonPage):
    @method
    class fill_loan_details(ItemElement):
        item_xpath = 'loan'

        obj_total_amount = CleanDecimal.SI(Dict('financialInformation/amountBorrowed/value'))
        obj_rate = CleanDecimal.SI(
            Dict('financialInformation/nextDuedateRate', default=NotAvailable),
            default=NotAvailable,
        )
        obj_subscription_date = Date(CleanText(Dict('contractCharacteristic/subscriptionDate')))
        obj_start_repayment_date = Date(CleanText(Dict('contractCharacteristic/firstPayoutDate')))
        obj_maturity_date = Date(CleanText(Dict('contractCharacteristic/closingDate')))
        obj_next_payment_amount = CleanDecimal.SI(Dict('financialInformation/nextDuedateAmount/value'))
        obj_next_payment_date = Date(CleanText(Dict('financialInformation/nextDuedateDate')))

        def obj_duration(self):
            duration = CleanText(Dict('financialInformation/duration'))(self)
            if not empty(duration):
                return int(duration)
            return NotAvailable


class PrepareReroutingPage(LoggedPage, JsonPage):
    def get_linebourse_redirection_data(self):
        return {
            'SJRToken': CleanText(Dict('characteristics/authenticationKeyValue'))(self.doc),
            'idClient': CleanText(Dict('characteristics/routingContext/value/formParameters/idClient'))(self.doc),
        }

    def get_extranet_redirection_data(self):
        return {
            'st': CleanText(Dict('characteristics/authenticationKeyValue'))(self.doc),
            'action': CleanText(Dict('characteristics/routingContext/value/formParameters/action'))(self.doc),
            'paramDA': CleanText(Dict('characteristics/routingContext/value/formParameters/paramDA'))(self.doc),
        }


class LinebourseReroutingPage(LoggedPage, JsonPage):
    pass


class ExtranetReroutingPage(LoggedPage, HTMLPage):
    pass


class LeaveLineBoursePage(RawPage):
    pass


class HistoryItem(ItemElement):
    klass = Transaction

    obj_label = CleanText(Dict('text'))

    def obj_date(self):
        date = Date(
            CleanText(Dict('dueDate'), default=NotAvailable),
            default=NotAvailable,
        )(self)

        if not date:
            return Field('rdate')(self)
        return date

    obj_rdate = Date(CleanText(Dict('date')))

    def obj_raw(self):
        # Redefine obj_raw so that parse_with_patterns method used in
        # FrenchTransaction can load date attribute properly (obj_date has to
        # be redefined, making its values being fetched after regular attributes).
        return Transaction.Raw(Dict('parsedData/originalText'))(self)

    obj_amount = CleanDecimal.SI(Dict('amount'))


class TransactionsPage(LoggedPage, JsonPage):
    def get_total_transactions_number(self):
        return int(Dict('meta/totalCount')(self.doc))

    @method
    class iter_history(DictElement):
        item_xpath = 'data'

        class item(HistoryItem):
            pass

    @method
    class iter_card_history(DictElement):
        item_xpath = 'data'

        class item(HistoryItem):
            def condition(self):
                # Skip comings
                return Date(CleanText(Dict('dueDate')))(self) <= date.today()

            obj_type = Transaction.TYPE_DEFERRED_CARD

    @method
    class iter_card_coming(DictElement):
        item_xpath = 'data'

        class item(HistoryItem):
            def condition(self):
                # Skip history
                return Date(CleanText(Dict('dueDate')))(self) > date.today()

            obj_type = Transaction.TYPE_DEFERRED_CARD


class ComingTransactionsPage(TransactionsPage):
    @method
    class iter_coming(DictElement):
        item_xpath = 'data'

        class item(ItemElement):
            klass = Transaction

            obj_label = CleanText(Dict('text'))
            obj_date = Date(CleanText(Dict('date')))
            obj_amount = CleanDecimal.SI(Dict('amount'))


class RevolvingHistoryPage(LoggedPage, JsonPage):
    @method
    class iter_history(DictElement):
        item_xpath = 'financialTransactions'

        class item(ItemElement):
            klass = Transaction

            obj_label = CleanText(Dict('label'))
            obj_date = Date(
                Regexp(
                    CleanText(Dict('date')),
                    r'(\d{4}-\d{2}-\d{2})',
                )
            )
            obj_amount = CleanDecimal.SI(Dict('amount/value'))


class MarketPage(LoggedPage, HTMLPage):
    # TODO: check if this code is still usable
    def is_error(self):
        return CleanText('//caption[contains(text(),"Erreur")]')(self.doc)

    def parse_decimal(self, td, percentage=False):
        value = CleanText('.')(td)
        if value and value != '-':
            if percentage:
                return Decimal(FrenchTransaction.clean_amount(value)) / 100
            return Decimal(FrenchTransaction.clean_amount(value))
        else:
            return NotAvailable

    def submit(self):
        form = self.get_form(nr=0)

        form.submit()

    def iter_investment(self):
        for tbody in self.doc.xpath('//table[@summary="Contenu du portefeuille valorisé"]/tbody'):
            inv = Investment()
            inv.label = CleanText('.')(tbody.xpath('./tr[1]/td[1]/a/span')[0])
            inv.code = CleanText('.')(tbody.xpath('./tr[1]/td[1]/a')[0]).split(' - ')[1]
            if is_isin_valid(inv.code):
                inv.code_type = Investment.CODE_TYPE_ISIN
            else:
                inv.code_type = NotAvailable
            inv.quantity = self.parse_decimal(tbody.xpath('./tr[2]/td[2]')[0])
            inv.unitvalue = self.parse_decimal(tbody.xpath('./tr[2]/td[3]')[0])
            inv.unitprice = self.parse_decimal(tbody.xpath('./tr[2]/td[5]')[0])
            inv.valuation = self.parse_decimal(tbody.xpath('./tr[2]/td[4]')[0])
            inv.diff = self.parse_decimal(tbody.xpath('./tr[2]/td[7]')[0])

            yield inv

    def get_valuation_diff(self, account):
        val = CleanText(self.doc.xpath('//td[contains(text(), "values latentes")]/following-sibling::*[1]'))
        account.valuation_diff = CleanDecimal(Regexp(val, r'([^\(\)]+)'), replace_dots=True)(self)

    def is_on_right_portfolio(self, account):
        return len(self.doc.xpath(
            '//form[@class="choixCompte"]//option[@selected and contains(text(), $id)]',
            id=account._info['id']
        ))

    def get_compte(self, account):
        return self.doc.xpath('//option[contains(text(), $id)]/@value', id=account._info['id'])[0]

    def come_back(self):
        link = Link('//div/a[contains(text(), "Accueil accès client")]', default=NotAvailable)(self.doc)
        if link:
            self.browser.location(link)


class LifeInsuranceHistory(LoggedPage, JsonPage):
    def build_doc(self, text):
        # If history is empty, there is no text
        if not text:
            return {}
        return super(LifeInsuranceHistory, self).build_doc(text)

    @method
    class iter_history(DictElement):
        def find_elements(self):
            return self.el or []  # JSON contains 'null' if no transaction

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                # Eliminate transactions without amount
                return Dict('montantBrut')(self)

            obj_raw = Transaction.Raw(Dict('type/libelleLong'))
            obj_amount = Eval(float_to_decimal, Dict('montantBrut/valeur'))

            def obj_date(self):
                date = Dict('dateEffet')(self)
                if date:
                    return datetime.fromtimestamp(date / 1000)
                return NotAvailable

            obj_vdate = obj_rdate = obj_date


class LifeInsuranceInvestments(LoggedPage, JsonPage):
    @method
    class iter_investment(DictElement):

        def find_elements(self):
            return self.el['repartition']['supports'] or []  # JSON contains 'null' if no investment

        class item(ItemElement):
            klass = Investment

            # For whatever reason some labels start with a '.' (for example '.INVESTMENT')
            obj_label = CleanText(Dict('libelleSupport'), replace=[('.', '')])
            obj_valuation = Eval(float_to_decimal, Dict('montantBrutInvesti/valeur'))

            def obj_portfolio_share(self):
                invested_percentage = Dict('pourcentageInvesti', default=None)(self)
                if invested_percentage:
                    return float_to_decimal(invested_percentage) / 100
                return NotAvailable

            # Note: the following attributes are not available for euro funds
            def obj_vdate(self):
                vdate = Dict('cotation/date')(self)
                if vdate:
                    return datetime.fromtimestamp(vdate / 1000)
                return NotAvailable

            def obj_quantity(self):
                if Dict('nombreParts')(self):
                    return Eval(float_to_decimal, Dict('nombreParts'))(self)
                return NotAvailable

            def obj_diff(self):
                if Dict('montantPlusValue/valeur', default=None)(self):
                    return Eval(float_to_decimal, Dict('montantPlusValue/valeur'))(self)
                return NotAvailable

            def obj_diff_ratio(self):
                if Dict('tauxPlusValue')(self):
                    return Eval(lambda x: float_to_decimal(x) / 100, Dict('tauxPlusValue'))(self)
                return NotAvailable

            def obj_unitvalue(self):
                if Dict('cotation/montant')(self):
                    return Eval(float_to_decimal, Dict('cotation/montant/valeur'))(self)
                return NotAvailable

            obj_code = IsinCode(CleanText(Dict('codeIsin', default='')), default=NotAvailable)
            obj_code_type = IsinType(CleanText(Dict('codeIsin', default='')))

    def is_contract_closed(self):
        return Dict('etatContrat/code')(self.doc) == "01"


class AppValidationPage(LoggedPage, XMLPage):
    def get_status(self):
        return CleanText('//response/status')(self.doc)


class SmsPage(LoggedPage, HTMLPage):
    pass


class CreditCooperatifMarketPage(LoggedPage, HTMLPage):
    # Stay logged when landing on the new Linebourse
    # (which is used by Credit Cooperatif's connections)
    # The parsing is done in linebourse.api.pages
    def is_error(self):
        return CleanText('//caption[contains(text(),"Erreur")]')(self.doc)


class RememberTerminalPage(LoggedPage, RawPage):
    pass
