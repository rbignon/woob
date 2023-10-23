# Copyright(C) 2022      Budget Insight
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

from datetime import date, datetime, timedelta
from base64 import b64decode
import re
import codecs

import requests

from woob.browser.pages import FormNotFound, LoggedPage, JsonPage, HTMLPage, RawPage, pagination
from woob.browser.elements import TableElement, method, ItemElement, DictElement
from woob.browser.filters.html import Attr, Link, TableCell
from woob.browser.filters.standard import (
    BrowserURL, CleanText, CleanDecimal, Coalesce, Currency, Date, Env, Eval,
    Field, Format, Lower, Map, MapIn, Regexp, Async, AsyncLoad, Base,
)
from woob.browser.filters.json import Dict
from woob.capabilities.bank import Loan, Account, AccountOwnership
from woob.capabilities.bank.base import Transaction
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.base import NotAvailable, empty
from woob.capabilities.bill import Subscription, Document, DocumentTypes
from woob.tools.capabilities.bank.investments import IsinCode, IsinType


class KeypadPage(JsonPage):
    def encode_password(self, password):
        decode_hex = codecs.getdecoder("hex_codec")

        keypad = self.get_keypad()
        # keypad = '63735393338303134323835323533663633313839393732673832303364353165313268343535356532643666366433346135343460333132616136653533373632643563643331313265393232693839303933643234656433333467343563323636603162353661353'

        encoded_keys, seed = keypad[:20], keypad[20:]
        # encoded_keys = '63735393338303134323'
        # seed = '835323533663633313839393732673832303364353165313268343535356532643666366433346135343460333132616136653533373632643563643331313265393232693839303933643234656433333467343563323636603162353661353'

        encoded_keys = encoded_keys[::-1]
        # encoded_keys = '32343130383339353736'

        keys = decode_hex(encoded_keys)[0].decode('utf-8')
        # keys = '2410839576' => virtual keyboard keys in order= 2 4 1 0 8 3 9 5 7 6

        mapped_password = self.map_password(keys, password)
        # we find the position of each password number in the keys
        # example password = '12345' => mapped_password = 2 0 5 1 7 = '20517'

        encoded_password = ''.join(mapped_password).encode("utf-8").hex()
        # we encode each number of the mapped password and concat in a string
        # 2 0 5 1 7 => 32 30 35 31 37 = '3230353137'

        encoded_password = encoded_password[::-1]
        # encoded_password = 7313530323

        # return encoded password + seed
        # example: '3230353137' + '835323533663633313839393732673832303364353165313268343535356532643666366433346135343460333132616136653533373632643563643331313265393232693839303933643234656433333467343563323636603162353661353'
        return encoded_password + seed

    def map_password(self, keys, password):
        return [str(keys.index(char)) for char in password]

    def get_keypad(self):
        return Dict('keypad')(self.doc)


CONTRACT_TYPES = {
    'particuliers': 'CLI',
    'professionnels': 'CLA',
}


class LoginPage(JsonPage):
    def get_website(self):
        return Dict('personType')(self.doc)

    def is_multispace(self):
        return len(self.doc['contracts']) > 1

    def get_error(self):
        return Dict('code')(self.doc), Dict('message')(self.doc)

    def get_authentication_data(self):
        return (
            Dict('accessToken')(self.doc),
            Dict('refreshToken')(self.doc),
            Dict('expiresAt')(self.doc),
            Dict('encryptedExpiresAt')(self.doc),
            Dict('userIdForBascule')(self.doc),
        )

    def get_user_id(self):
        return Dict('userId')(self.doc)

    def get_contract_id(self, website):
        contract_type = CONTRACT_TYPES[website]
        contracts = Dict('contracts')(self.doc)
        for contract in contracts:
            if contract['type'] == contract_type:
                return contract['id']

        # when there isn't one, the website uses '0000000000000000' instead
        # ps: when looking at the request we won't find '0000000000000000' but 'MDAwMDAwMDAwMDAwMDAwMA'
        #     the base64 encoding of it
        return '0000000000000000'

    def get_user_name(self):
        return Coalesce(
            Dict('userName', default=NotAvailable),
            Format(
                '%s %s',
                Dict('firstName', default=NotAvailable),
                Dict('lastName', default=NotAvailable)
            )
        )(self.doc)

    def get_mfa_details(self):
        return (
            Dict('multiFactorAuth/type', default=NotAvailable)(self.doc),
            Dict('multiFactorAuth/device/name', default=NotAvailable)(self.doc),
        )


class PreAccessPage(LoggedPage, JsonPage):
    # needs to be a logged page to avoid re-login
    pass


class LaunchRedirectionPage(LoggedPage, HTMLPage):
    def get_message(self):
        return CleanText('//form[@id="mainForm"]/div[1]')(self.doc)


class RedirectionPage(HTMLPage):
    def go_pre_home(self):
        form = self.get_form(id='form')
        form.submit()


class PreHomePage(HTMLPage):
    def go_home(self):
        form = self.get_form(id='form')
        form.submit()


class HomePage(LoggedPage, RawPage):
    pass


class RedirectMonEspaceHome(LoggedPage, RawPage):
    pass


class MonEspaceHome(LoggedPage, RawPage):
    pass


class AggregationPage(LoggedPage, JsonPage):
    pass


ACCOUNT_TYPES = {
    'Compte Courant': Account.TYPE_CHECKING,
    'Compte de dépôts': Account.TYPE_DEPOSIT,
    'Livret A': Account.TYPE_SAVINGS,
    'Livret Dév. Durable et Solidaire': Account.TYPE_SAVINGS,
    'Compte de nantissement': Account.TYPE_SAVINGS,
    'Livret de Dév. Durable et Solidaire': Account.TYPE_SAVINGS,
    "Plan d'Epargne en Actions": Account.TYPE_PEA,
    "Plan d'Epargne en Actions - Bourse Expert": Account.TYPE_PEA,
    'Compte sur livret': Account.TYPE_SAVINGS,
    'OPTILION STRATEGIQUE': Account.TYPE_SAVINGS,
    'Compte épargne logement': Account.TYPE_SAVINGS,
    'Compte Commun': Account.TYPE_CHECKING,
}


ACCOUNT_OWNERSHIP = {
    'holder': AccountOwnership.OWNER,
    'coholder': AccountOwnership.CO_OWNER,
    'minor_representative': AccountOwnership.ATTORNEY,
}


class AccountOwnershipItemElement(ItemElement):
    obj__user_role = NotAvailable  # overwrite if available

    def get_ownership(self, owner):
        if re.search(r'(m|mr|me|mme|mlle|mle|ml)\.? (.*)\bou (m|mr|me|mme|mlle|mle|ml)\b(.*)', owner, re.IGNORECASE):
            return AccountOwnership.CO_OWNER
        elif 'user_name' in self.env and self.env['user_name'] in owner:
            return AccountOwnership.OWNER
        return NotAvailable

    def obj_ownership(self):
        user_role = Field('_user_role')(self)
        if not empty(user_role):
            return user_role

        return Eval(
            self.get_ownership,
            Coalesce(
                CleanText(Dict('holder_name', default='')),
                CleanText(Dict('holder_label', default='')),
                Format(
                    '%s %s',
                    CleanText(Dict('holder/first_name', default='')),
                    CleanText(Dict('holder/last_name', default='')),
                ),
            )
        )(self)


class AccountItem(AccountOwnershipItemElement):
    klass = Account

    obj_number = obj_id = CleanText(Dict('external_id'), replace=[(' ', '')])
    obj_label = CleanText(Dict('label'))
    obj_balance = CleanDecimal.SI(Dict('amount/value'))
    obj_currency = Currency(Dict('amount/currency'))
    obj_iban = CleanText(Dict('iban', default=''), default=NotAvailable)
    obj_type = Map(Field('label'), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)
    obj__user_role = Map(Lower(Dict('user_role', default='')), ACCOUNT_OWNERSHIP, NotAvailable)
    obj__internal_id = CleanText(Dict('internal_id'))
    obj__transfer_id = None
    obj__market_link = None


class AccountsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):
        item_xpath = 'accounts'

        class item(AccountItem):
            def obj_type(self):
                provided_account_types = {'current': Account.TYPE_CHECKING, 'saving': Account.TYPE_SAVINGS}
                provided_type = CleanText(Dict('type', default=''), default=NotAvailable)(self)
                if provided_type in provided_account_types:
                    return provided_account_types.get(provided_type)

                # fallback to use the label field to type
                return Map(Field('label'), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)

    @method
    class iter_subscriptions(DictElement):
        item_xpath = 'accounts'

        class item(ItemElement):
            klass = Subscription

            def condition(self):
                # we take documents from checking account only
                return Dict('type')(self) == 'current'  # yes current means checking^^

            obj_id = CleanText(Dict('external_id'), replace=[(' ', '')])
            obj_label = CleanText(Dict('label'))
            obj_subscriber = CleanText(Dict('holder_label'))


class DocumentsPage(LoggedPage, JsonPage):
    @method
    class iter_documents(DictElement):
        class item(ItemElement):
            klass = Document

            def condition(self):
                return CleanText(Dict('numcptclicl'))(self) in Env('subid')(self)

            obj_id = Format(
                "%s%s%s_%s",
                Dict("numageclicl"),
                Dict("numcptclicl"),
                Dict("codlccpt"),
                Dict("datprddoccli"),
            )
            obj_date = Date(Dict('datprddoccli'))
            obj_format = 'pdf'
            obj_url = BrowserURL('download_document', token=Dict('downloadToken'))
            obj_type = DocumentTypes.STATEMENT


class TermAccountsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):
        item_xpath = 'term_accounts'

        class item(AccountItem):
            obj_number = obj_id = CleanText(Dict('contract_id'))
            obj_type = Account.TYPE_SAVINGS
            obj__internal_id = NotAvailable


class CardsPage(LoggedPage, JsonPage):
    @method
    class iter_cards(DictElement):
        item_xpath = None

        class item(AccountOwnershipItemElement):
            klass = Account

            # obj_id will be overwritten in `CardDetailsPage` to match cards already existing in the database
            # obj__id will be used in `iter_history`
            obj_id = obj__id = CleanText(Dict('id'))
            obj_label = Format('%s %s', CleanText(Dict('product/label')), CleanText(Dict('holder/name')))
            obj_balance = CleanDecimal.SI(Dict('amount/value'))
            obj_currency = Currency(Dict('amount/currency'))
            obj_type = Account.TYPE_CARD
            obj__transfer_id = None
            obj__market_link = None
            obj__internal_id = CleanText(Dict('internal_id'))
            obj__parent_internal_id = CleanText(Dict('account_internal_id'))

            def obj_number(self):
                card_id = Field('id')(self)
                decoded_card_id = b64decode(f'{card_id}=='.encode('ascii')).decode('ascii')

                # decoded_card_id can have one of these 2 formats:
                #     - _50102797621X695
                #     - _50102797621X695-01351028369F
                if len(decoded_card_id) > 16:
                    if decoded_card_id[16] == '-':
                        decoded_card_id = decoded_card_id[:16]
                    else:
                        raise AssertionError('Unexpected number format')

                return decoded_card_id


class CardSynthesisPage(LoggedPage, JsonPage):
    def is_card_available(self, card_internal_id):
        for account in self.doc.get('accounts', []):
            for card in account.get('bank_cards', []):
                if card['card_contract_id'] == card_internal_id:
                    return True
        return False


class CardDetailsPage(LoggedPage, JsonPage):
    @method
    class fill_card(ItemElement):
        klass = Account

        obj_number = CleanText(Dict('masked_pan'))

        def obj_id(self):
            last_numbers = Field('number')(self)[-3:]
            agency_code = CleanText(Dict('agency_code'))(self)
            account_number = CleanText(Dict('account_number'))(self)
            return agency_code + account_number[-7:] + '-' + last_numbers


class LifeInsurancesPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):
        item_xpath = 'life_insurance'

        class item(AccountItem):
            obj_number = obj_id = CleanText(Dict('contract_id'))
            obj_type = Account.TYPE_LIFE_INSURANCE
            obj__partner_label = CleanText(Dict('partner/label', default=''))
            obj__partner_code = CleanText(Dict('partner/code', default=''))
            obj__has_details = Dict('tops/unplugging_consultation')


class ForbiddenLifeInsurancesPage(LoggedPage, HTMLPage):
    pass


LOAN_TYPES = {
    'CPS': Account.TYPE_REVOLVING_CREDIT,
    'COS': Account.TYPE_CONSUMER_CREDIT,
    'CIT': Account.TYPE_MORTGAGE,
}


class LoansPage(LoggedPage, JsonPage):
    @method
    class iter_loans(DictElement):
        item_xpath = 'credits'

        class item(ItemElement):
            klass = Loan

            def condition(self):
                loan_type = CleanText(Dict('source_code'))(self.el)

                # From JS file: https://monespace.lcl.fr/projects_front_src_app_home_synthesis_synthesis_module_ts.53d9ecf1bc5b754c.js
                # MORTGAGE="CIT"
                # AUTHORIZED_OVERDRAFT="DAU"
                # REVOLVING_CREDIT="CPS"
                # CONSUMER_CREDIT="COS"
                # PRO_DIFFERRED_REGLEMENT_CREDIT="CRD"
                # PRO_ORDER_AUTHORIZED_CREDIT="OCA"

                if loan_type in ('DAU', 'CIN', 'CRD'):
                    # we skip accounts not shown on website
                    self.logger.warning('Skip an Overdraft account')
                    return False
                self.logger.info('LCL: loan account found  %s', loan_type)
                return True

            obj_id = CleanText(Dict('id'))
            obj_label = CleanText(Dict('label'))
            obj_total_amount = CleanDecimal.SI(Dict('amount'))
            obj_currency = Currency(Dict('currency'))

            def obj_type(self):
                loan_type = Map(Field('_source_code'), LOAN_TYPES, Account.TYPE_UNKNOWN)(self)
                if loan_type == Account.TYPE_UNKNOWN:
                    self.logger.warning(
                        'loan _source_code %s is still untyped, please type it.', Field('_source_code')(self)
                    )
                return loan_type or Account.TYPE_LOAN

            obj__source_code = CleanText(Dict('source_code'))
            obj__product_code = CleanText(Dict('product_code'))
            obj__branch = CleanText(Dict('branch'))
            obj__account = CleanText(Dict('account'))
            obj__legacy_id = Format(
                '0%s0%s%s%s',
                Field('_branch'),
                Field('_account'),
                CleanText(Dict('key_letter')),
                CleanText(Field('label'), replace=[(' ', '')]),
            )
            obj__transfer_id = None
            obj__market_link = None

            def obj__parent_id(self):
                branch = Field('_branch')(self)
                account = Field('_account')(self)
                key_letter = CleanText(Dict('key_letter'))(self)

                if len(account) == 4:
                    # pad to length 5
                    account = '0' + account

                return f'0{branch}0{account}{key_letter}'


class LoanDetailsPage(LoggedPage, JsonPage):
    @method
    class fill_loan(ItemElement):
        klass = Loan

        obj_available_amount = CleanDecimal.SI(Dict('available_amount'))  # amount not unlocked yet
        obj_balance = Eval(
            lambda x, y: -(x + y),
            Field('available_amount'),
            CleanDecimal.SI(Dict('outstanding_capital'))  # unlocked amount
        )
        obj_rate = CleanDecimal.SI(Dict('eir'))
        obj_next_payment_amount = CleanDecimal.SI(Dict('next_due_date_amount'))
        obj_next_payment_date = Date(CleanText(Dict('next_due_date', default='')), default=NotAvailable)
        obj__iban = CleanText(Dict('iban', default=''), default=NotAvailable)

        def obj_maturity_date(self):
            maturity_date = Date(CleanText(Dict('final_due_date', default='')), default=NotAvailable)(self)
            if not maturity_date:
                # last_due_date acts like final_due_date only when this key is missing in json's response
                return Date(CleanText(Dict('last_due_date', default='')), default=NotAvailable)(self)
            return maturity_date

        def obj_last_payment_date(self):
            last_payment_date = Date(CleanText(Dict('last_due_date', default='')), default=NotAvailable)(self)
            if not last_payment_date or last_payment_date > date.today():
                return NotAvailable  # here last_due_date is the date of the very last payment
            return last_payment_date  # here it's the date of the previous payment

        def obj_last_payment_amount(self):
            if not Field('last_payment_date')(self):
                return NotAvailable  # here last_due_date_amount is the very last amount that will be paid
            return CleanDecimal.SI(Dict('last_due_date_amount'))(self)  # here it's the previous amount paid


TRANSACTION_TYPES = {
    'virement': Transaction.TYPE_TRANSFER,
    'vir sepa': Transaction.TYPE_TRANSFER,
    'prelvt': Transaction.TYPE_BANK,
    'prlv sepa': Transaction.TYPE_ORDER,
    'cb': Transaction.TYPE_CARD,
    'cotisation': Transaction.TYPE_BANK,
    'abon lcl': Transaction.TYPE_BANK,
}


class TransactionItem(ItemElement):
    klass = Transaction

    obj_label = CleanText(Dict('label'))
    obj_amount = CleanDecimal.SI(Dict('amount/value'))
    obj_date = Date(
        Regexp(
            CleanText(Dict('booking_date_time')),
            r'(.*)T',
        )
    )
    obj_type = MapIn(
        Lower(Field('label')),
        TRANSACTION_TYPES,
        Transaction.TYPE_UNKNOWN,
    )

    def obj__details_available(self):
        details_available = CleanText(Dict('are_details_available', default=''))(self)
        return details_available == 'True'

    def obj__is_accounted(self):
        is_accounted = CleanText(Dict('is_accounted', default=''))(self)
        return is_accounted == 'True'


class TransactionsPage(LoggedPage, JsonPage):
    def update_stop_condition(self):
        # if the number 100 is changed, we should do the same in the browser
        return len(self.doc['accountTransactions']) < 100

    @method
    class iter_transactions(DictElement):
        item_xpath = 'accountTransactions'

        class item(TransactionItem):
            # there's an id field but it is not unique
            pass


class SEPAMandatePage(LoggedPage, JsonPage):
    def update_stop_condition(self):
        # if the number 100 is changed, we should do the same in the browser
        return int(self.doc['total_size']) < 100

    @method
    class iter_transactions(DictElement):
        item_xpath = 'elements'

        class item(TransactionItem):
            obj_label = Format('%s %s', CleanText(Dict('creditor')), CleanText(Dict('mandate')))
            obj_amount = CleanDecimal.SI(Dict('amount'))
            obj_date = Date(
                Regexp(
                    CleanText(Dict('date')),
                    r'(.*)T',
                )
            )
            obj_type = Transaction.TYPE_TRANSFER


class CardTransactionsPage(LoggedPage, JsonPage):
    @method
    class iter_transactions(DictElement):
        item_xpath = None

        class item(TransactionItem):
            def obj_type(self):
                if 'Relevés Carte bancaire' in Field('label')(self):
                    return Transaction.TYPE_CARD_SUMMARY
                return Transaction.TYPE_DEFERRED_CARD


class RoutagePage(LoggedPage, HTMLPage):
    def send_form(self):
        form = self.get_form()
        return form.submit()


class GetContractPage(LoggedPage, HTMLPage):
    pass


class AVInvestmentsPage(LoggedPage, JsonPage):
    def update_life_insurance_account(self, life_insurance):
        life_insurance._owner = Format(
            '%s %s',
            Dict('situationAdministrativeEpargne/lppeoscp'),
            Dict('situationAdministrativeEpargne/lnpeoscp'),
        )(self.doc)
        life_insurance.label = '%s %s' % (
            Dict('situationAdministrativeEpargne/lcofc')(self.doc),
            life_insurance._owner,
        )
        life_insurance.valuation_diff = CleanDecimal(
            Dict('situationFinanciereEpargne/mtpmvcnt'),
            default=NotAvailable
        )(self.doc)
        return life_insurance

    @method
    class iter_investment(DictElement):
        item_xpath = 'listeSupports/support'

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(Dict('lcspt'))
            obj_valuation = CleanDecimal(Dict('mtvalspt'))
            obj_code = CleanText(Dict('cdsptisn'), default=NotAvailable)
            obj_unitvalue = CleanDecimal(Dict('mtliqpaaspt'), default=NotAvailable)
            obj_quantity = CleanDecimal(Dict('qtpaaspt'), default=NotAvailable)
            obj_diff = CleanDecimal(Dict('mtpmvspt'), default=NotAvailable)
            obj_vdate = Date(Dict('dvspt'), default=NotAvailable)
            obj_code_type = IsinType(Field('code'))

            def obj_portfolio_share(self):
                ptf = CleanDecimal(Dict('txrpaspt'), default=NotAvailable)(self)
                if empty(ptf):
                    return NotAvailable
                ptf /= 100
                return ptf


class AVHistoryPage(LoggedPage, JsonPage):
    @method
    class iter_history(DictElement):
        item_xpath = 'listeOperations'

        class item(ItemElement):
            klass = Transaction

            obj_label = CleanText(Dict('lcope'))
            obj_amount = CleanDecimal(Dict('mtope'))
            obj_type = Transaction.TYPE_BANK
            obj_investments = NotAvailable

            # The 'idope' key contains a string such as "70_ABC666ABC   2018-03-182018-03-16-20.55.27.960852"
            # 70= N° transaction, 6660666= N° account, 2018-03-18= date and 2018-03-16=rdate.
            # We thus use "70_ABC666ABC" for the transaction ID.

            obj_id = Regexp(CleanText(Dict('idope')), r'(\d+_[\dA-Z]+)')

            def obj__dates(self):
                raw = CleanText(Dict('idope'))(self)
                m = re.findall(r'\d{4}-\d{2}-\d{2}', raw)
                # We must verify that the two dates are correctly fetched
                assert len(m) == 2
                return m

            def obj_date(self):
                return Date().filter(Field('_dates')(self)[0])

            def obj_rdate(self):
                return Date().filter(Field('_dates')(self)[1])


class NoPermissionPage(LoggedPage, HTMLPage):
    def get_error_msg(self):
        error_msg = CleanText(
            '//div[@id="divContenu"]//div[@id="attTxt" and contains(text(), "vous n\'avez pas accès à cette opération")]'
        )(self.doc)
        return error_msg


class DiscPage(LoggedPage, HTMLPage):
    def on_load(self):
        try:
            # when life insurance access is restricted, a complete lcl logout form is present, don't use it
            # and sometimes there's just no form
            form = self.get_form(xpath='//form[not(@id="formLogout")]')
            form.submit()
        except FormNotFound:
            # Sometime no form is present, just a redirection
            self.logger.debug('no form on this page')

        super(DiscPage, self).on_load()


class BoursePreLoadPage(LoggedPage, HTMLPage):
    pass


class BourseHomePage(LoggedPage, HTMLPage):
    pass


MARKET_TRANSACTION_TYPES = {
    'VIREMENT': Transaction.TYPE_TRANSFER,
}


class BoursePage(LoggedPage, HTMLPage):
    ENCODING = 'latin-1'
    REFRESH_MAX = 0

    TYPES = {
        'plan épargne en actions': Account.TYPE_PEA,
        "plan d'épargne en actions": Account.TYPE_PEA,
        'plan épargne en actions bourse': Account.TYPE_PEA,
        "plan d'épargne en actions bourse": Account.TYPE_PEA,
        'pea pme bourse': Account.TYPE_PEA,
        'pea pme': Account.TYPE_PEA,
        'pea bourse expert': Account.TYPE_PEA,
    }

    def on_load(self):
        """
        Sometimes we are directed towards a prior html page before accessing Bourse Page.
        Submit the form to access the page that contains the Bourse Page's session cookie.
        """
        try:
            form = self.get_form(id='form')
        except FormNotFound:  # already on the targetted page
            pass
        else:
            form.submit()

        super(BoursePage, self).on_load()

    def open_iframe(self):
        # should be done always (in on_load)?
        for iframe in self.doc.xpath('//iframe[@id="mainIframe"]'):
            self.browser.location(iframe.attrib['src'])
            break

    def password_required(self):
        return CleanText(
            '//b[contains(text(), "Afin de sécuriser vos transactions, nous vous invitons à créer un mot de passe trading")]'
        )(self.doc)

    def get_next(self):
        if 'onload' in self.doc.xpath('.//body')[0].attrib:
            return re.search('"(.*?)"', self.doc.xpath('.//body')[0].attrib['onload']).group(1)

    def get_fullhistory(self):
        form = self.get_form(id="historyFilter")
        form['cashFilter'] = "ALL"
        # We can't go above 2 years
        form['beginDayfilter'] = (
            datetime.strptime(form['endDayfilter'], '%d/%m/%Y') - timedelta(days=730)
        ).strftime('%d/%m/%Y')
        form.submit()

    @method
    class get_list(TableElement):
        item_xpath = '//table[has-class("tableau_comptes_details")]//tr[td and not(parent::tfoot)]'
        head_xpath = '//table[has-class("tableau_comptes_details")]/thead/tr/th'

        col_label = 'Comptes'
        col_owner = re.compile('Titulaire')
        col_titres = re.compile('Valorisation')
        col_especes = re.compile('Solde espèces')

        class item(AccountOwnershipItemElement):
            klass = Account

            load_details = Field('_market_link') & AsyncLoad

            obj__especes = CleanDecimal(TableCell('especes'), replace_dots=True, default=0)
            obj__titres = CleanDecimal(TableCell('titres'), replace_dots=True, default=0)
            obj_valuation_diff = Async('details') & CleanDecimal(
                '//td[contains(text(), "value latente")]/following-sibling::td[1]',
                replace_dots=True,
            )
            obj__market_id = Regexp(Attr(TableCell('label'), 'onclick'), r'nump=(\d+:\d+)')
            obj__market_link = Regexp(Attr(TableCell('label'), 'onclick'), r"goTo\('(.*?)'")
            obj__link_id = Async('details') & Link(u'//a[text()="Historique"]')
            obj__transfer_id = None
            obj__internal_id = NotAvailable
            obj_balance = Field('_titres')
            obj_currency = Currency(CleanText(TableCell('titres')))

            def obj_number(self):
                number = CleanText((TableCell('label')(self)[0]).xpath('./div[not(b)]'))(self).replace(' - ', '')
                m = re.search(r'(\d{11,})[A-Z]', number)
                if m:
                    number = m.group(0)
                return number

            def obj_id(self):
                return "%sbourse" % Field('number')(self)

            def obj_label(self):
                return "%s Bourse" % CleanText((TableCell('label')(self)[0]).xpath('./div[b]'))(self)

            def obj_type(self):
                _label = ' '.join(Field('label')(self).split()[:-1]).lower()
                for key in self.page.TYPES:
                    if key in _label:
                        return self.page.TYPES.get(key)
                return Account.TYPE_MARKET

            def obj_ownership(self):
                owner = CleanText(TableCell('owner'))(self)
                return self.get_ownership(owner)

    def get_logout_link(self):
        return Link('//a[contains(text(), "Retour aux comptes")]')(self.doc)

    @method
    class iter_investment(TableElement):
        item_xpath = '//table[@id="tableValeurs"]/tbody/tr[@id and count(descendant::td) > 1]'
        head_xpath = '//table[@id="tableValeurs"]/thead/tr/th'

        col_label = 'Valeur / Isin'
        col_quantity = re.compile('Quantit|Qt')
        col_unitprice = re.compile(r'Prix de revient')
        col_unitvalue = 'Cours'
        col_valuation = re.compile(r'Val(.*)totale')  # 'Val. totale' or 'Valorisation totale'
        col_diff = re.compile(r'\+/- Value latente')
        col_diff_percent = 'Perf'

        class item(ItemElement):
            klass = Investment

            obj_label = Base(TableCell('label'), CleanText('./following-sibling::td[1]//a'))
            obj_code = Base(
                TableCell('label'),
                IsinCode(
                    Regexp(
                        CleanText('./following-sibling::td[1]//br/following-sibling::text()', default=NotAvailable),
                        pattern='^([^ ]+).*',
                        default=NotAvailable
                    ),
                    default=NotAvailable
                ),
            )
            obj_code_type = IsinType(Field('code'))
            obj_quantity = Base(
                TableCell('quantity'),
                CleanDecimal.French('./span', default=NotAvailable),
            )
            obj_diff = Base(
                TableCell('diff'),
                CleanDecimal.French('./span', default=NotAvailable),
            )
            # In some cases (some PEA at least) valuation column is missing
            obj_valuation = CleanDecimal.French(TableCell('valuation', default=''), default=NotAvailable)

            def obj_diff_ratio(self):
                if TableCell('diff_percent', default=None)(self):
                    diff_percent = Base(
                        TableCell('diff_percent'),
                        CleanDecimal.French('.//span', default=NotAvailable),
                    )(self)
                    if not empty(diff_percent):
                        return diff_percent / 100
                return NotAvailable

            def obj_original_currency(self):
                unit_value = Base(
                    TableCell('unitvalue'), CleanText('./br/preceding-sibling::text()', default=NotAvailable)
                )(self)
                if "%" in unit_value:
                    return NotAvailable

                currency = Base(
                    TableCell('unitvalue'), Currency('./br/preceding-sibling::text()', default=NotAvailable)
                )(self)
                if currency == Env('account_currency')(self):
                    return NotAvailable
                return currency

            def obj_unitvalue(self):
                # In the case where the account currency is different from the investment one
                if Field('original_currency')(self):
                    return NotAvailable
                unit_value = Base(
                    TableCell('unitvalue'), CleanText('./br/preceding-sibling::text()', default=NotAvailable)
                )(self)
                # Check if the unitvalue and unitprice are in percentage
                if "%" in unit_value and "%" in CleanText(TableCell('unitprice', default=''))(self):
                    # In the unitprice of the page, there can be a value in percent
                    # and still return NotAvailable due to parsing failure
                    # (if it happens, a new case need to be treated)
                    if not Field('unitprice')(self):
                        return NotAvailable
                    # Convert the percentage to ratio
                    # So the valuation can be equal to quantity * unitvalue
                    return Eval(
                        lambda x: x / 100,
                        Base(TableCell('unitvalue'), CleanDecimal.French('./br/preceding-sibling::text()'))(self)
                    )(self)

                return Base(
                    TableCell('unitvalue'), CleanDecimal.French('./br/preceding-sibling::text()', default=NotAvailable)
                )(self)

            def obj_original_unitvalue(self):
                if not Field('original_currency')(self):
                    return NotAvailable
                return Base(
                    TableCell('unitvalue'),
                    CleanDecimal.French('./br/preceding-sibling::text()', default=NotAvailable)
                )(self)

            def obj_unitprice(self):
                unit_value = Base(
                    TableCell('unitvalue'), CleanText('./br/preceding-sibling::text()', default=NotAvailable)
                )(self)
                if "%" in unit_value and "%" in CleanText(TableCell('unitprice', default=''))(self):
                    # unit price (in %) is displayed like this : 1,00 (100,00%)
                    # Retrieve only the first value.
                    return CleanDecimal.French(
                        Regexp(
                            CleanText(TableCell('unitprice')),
                            pattern='^(\\d+),(\\d+)',
                            default=''
                        ),
                        default=NotAvailable
                    )(self)
                # Sometimes (for some PEA at least) unitprice column isn't returned by LCL
                return CleanDecimal.French(TableCell('unitprice', default=NotAvailable))(self)

    @pagination
    @method
    class iter_history(TableElement):
        item_xpath = '//table[@id="historyTable" and thead]/tbody/tr'
        head_xpath = '//table[@id="historyTable" and thead]/thead/tr/th'

        col_date = 'Date'
        col_label = u'Opération'
        col_quantity = u'Qté'
        col_code = u'Libellé'
        col_amount = 'Montant'

        def next_page(self):
            form = self.page.get_form(id="historyFilter")
            form['PAGE'] = int(form['PAGE']) + 1
            if self.page.doc.xpath('//*[@data-page = $page]', page=form['PAGE']):
                return requests.Request("POST", form.url, data=dict(form))

        class item(ItemElement):
            klass = Transaction

            obj_date = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_type = MapIn(Field('label'), MARKET_TRANSACTION_TYPES, Transaction.TYPE_BANK)
            obj_amount = CleanDecimal(TableCell('amount'), replace_dots=True)
            obj_investments = Env('investments')

            def obj_label(self):
                return TableCell('label')(self)[0].xpath('./text()')[0].strip()

            def parse(self, el):
                i = None
                self.env['investments'] = []

                if CleanText(TableCell('code'))(self):
                    i = Investment()
                    i.label = Field('label')(self)
                    i.code = TableCell('code')(self)[0].xpath('./text()[last()]')[0].strip()
                    i.quantity = CleanDecimal.French(TableCell('quantity'), default=NotAvailable)(self)
                    i.valuation = Field('amount')(self)
                    i.vdate = Field('date')(self)

                    self.env['investments'] = [i]
