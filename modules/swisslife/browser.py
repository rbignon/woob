# Copyright(C) 2012-2021  Powens
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

from requests.exceptions import ReadTimeout

from woob.browser import URL, need_login
from woob.browser.mfa import TwoFactorBrowser
from woob.browser.exceptions import ClientError
from woob.exceptions import (
    ActionNeeded, ActionType, AppValidationExpired, BrowserIncorrectPassword,
    BrowserHTTPError, SentOTPQuestion, OTPSentType, BrowserUnavailable,
    BrowserHTTPNotFound, BrowserUserBanned,
)
from woob.browser.exceptions import ServerError
from woob.capabilities.bank import Account
from woob.capabilities.bank.wealth import Per, PerVersion, Investment, Pocket
from woob.capabilities.base import NotAvailable, empty
from woob.capabilities.captcha import RecaptchaV2Question
from woob.tools.capabilities.bank.transactions import sorted_transactions
from woob.tools.decorators import retry

from .pages import (
    ProfilePage, AccountsPage, AccountDetailPage, AccountVieEuroPage, InvestmentPage,
    AccountVieUCCOPage, AccountVieUCCODetailPage, AccountVieUCPage, BankAccountDetailPage,
    BankAccountTransactionsPage, MaintenancePage, AuthenticationPage, PhoneNumber,
    HandleSMSPage
)


class SwisslifeBrowser(TwoFactorBrowser):
    phone_number = URL(
        r'/api/v4/nest/personne/mfa/getPhoneNumberAndApporteur\?tokenCaptcha=(?P<tokenCaptcha>.*)',
        PhoneNumber
    )
    send_sms_page = URL(r'/api/v4/nest/personne/mfa/sendMfaSmsOtp')
    handle_sms_page = URL(r'/api/v4/nest/personne/mfa/checkMfaOtp', HandleSMSPage)
    authenticate = URL(r'/api/v3/authenticate', AuthenticationPage)
    profile = URL(r'/api/v3/personne', ProfilePage)
    accounts = URL(r'/api/v3/contrat/home', AccountsPage)
    investment = URL(r'/api/v3/contrat/.*/encours.*', InvestmentPage)
    bank_account_detail = URL(r'/api/v3/contrat/detail/(?P<id>.*)', BankAccountDetailPage)
    bank_account_transactions = URL(
        r'/api/v3/contrat/operationListe/(?P<account_id>.+)/(?P<index>\d+)/(?P<size>\d+)$',
        BankAccountTransactionsPage
    )
    account_vie_ucco_detail = URL(r'/api/v3/contrat/.*/operations.*', AccountVieUCCODetailPage)
    account_vie_ucco = URL(r'/api/v3/contrat/(?P<id>.*)\?typeContrat=ADHERENT', AccountVieUCCOPage)
    account_detail = URL(
        r'/api/v3/contrat/(?P<id>.*)',
        r'/api/v3/contrat/(?P<id>.*)/encours\?codeProfil=(?P<profile_type>.*)',
        AccountDetailPage
    )
    account_vie_euro = URL(r'/api/v3/contratVieEuro/(?P<id>.*)', AccountVieEuroPage)
    account_vie_uc = URL(r'/api/v3/contratVieucEntreprise/.*', AccountVieUCPage)

    maintenance = URL(r'/api/v3/authenticate', MaintenancePage)

    HAS_CREDENTIALS_ONLY = True

    __states__ = ('mfauuid',)

    def __init__(self, config, domain, *args, **kwargs):
        super(SwisslifeBrowser, self).__init__(config, *args, **kwargs)
        self.config = config

        # use to bypass captcha and sca for 90 days
        self.mfauuid = None

        self.BASEURL = 'https://%s' % (domain if '.' in domain else 'myswisslife.fr')
        self.session.headers['X-Requested-With'] = 'XMLHttpRequest'
        self.session.headers['Accept'] = 'application/json, text/javascript, */*; q=0.01'

        self.AUTHENTICATION_METHODS = {
            'sms': self.handle_sms,
        }

    @retry(ReadTimeout)
    def do_authentication(self, data):
        cookies = {'mfaUuid': self.mfauuid}
        # Retry needed to avoid random timeouts while trying to login on '/api/v3/authenticate'
        self.location('/api/v3/authenticate', data=data, cookies=cookies)

    def init_login(self):
        try:
            data = {'username': self.username, 'password': self.password, 'media': 'web', 'rememberMe': 'true'}
            self.do_authentication(data)
            # handle case with captcha and SMS SCA
            # the else case : no Captcha/SCA
            captcha_response = self.config['captcha_response'].get()
            if captcha_response:
                self.phone_number.go(tokenCaptcha=captcha_response)
                # check for SMS SCA
                if self.phone_number.is_here():
                    if self.page.phone_is_valid():
                        self.phone_number = self.page.get_phone_number()
                        self.check_interactive()
                        self.send_sms()

                    # else case : phone not valid (message generated by js)
                    raise ActionNeeded(
                        locale="fr-FR",
                        message='Nous ne pouvons pas vous adresser le code confidentiel pour accéder à votre compte. '
                        + 'Nous vous invitons à contacter votre service client au 09 74 75 76 76.',
                        action_type=ActionType.CONTACT,
                    )

            elif self.page.is_captcha():
                raise RecaptchaV2Question(
                    website_key='6LdAI0AUAAAAALk4lT524tHE-J9fgJ0ofbVuN8lH',
                    website_url='https://myswisslife.fr/connection/login'
                )

        except ClientError:
            raise BrowserIncorrectPassword("Votre identifiant utilisateur est inconnu ou votre mot de passe est incorrect.")
        except ServerError as e:
            error = e.response.json().get('error')
            if error:
                raise BrowserUnavailable()
            raise

        if self.maintenance.is_here():
            # If the website is in maintenance, we are redirected to a HTML page
            raise BrowserUnavailable(self.page.get_error_message())

    def send_sms(self):
        self.send_sms_page.go(method='POST')

        raise SentOTPQuestion(
            'sms',
            medium_type=OTPSentType.SMS,
            message=f'Veuillez entrer le code reçu au numéro : {self.phone_number}',
        )

    def handle_sms(self):
        try:
            self.handle_sms_page.go(json={'otp': self.sms, 'rememberMfa': 'true'})
        except ClientError as e:
            if e.response.status_code == 401 and 'AuthentifieSessionExpire' in e.response.text:
                raise AppValidationExpired()
            raise

        if not self.page.is_valid():
            if self.page.is_blocked():
                raise BrowserUserBanned()
            raise BrowserIncorrectPassword()

        self.mfauuid = self.session.cookies.get('mfaUuid')

    @need_login
    def go_to_account(self, account):
        # For some accounts, we get a 500 error even on the website...
        # These accounts have no balance so we do not fetch them.
        try:
            self.location(account.url)
        except ServerError as e:
            # Some accounts sometimes return 503, we can try again
            if e.response.status_code == 503:
                try:
                    self.accounts.go()
                    self.location(account.url)
                except ServerError as e:
                    if e.response.status_code == 503:
                        raise BrowserUnavailable()
                else:
                    return True
            self.logger.warning('Server Error: could not fetch the details for account %s.', account.label)
        except ClientError as e:
            # Some accounts return 403 forbidden and don't appear on the website
            if e.response.status_code == 403:
                self.logger.warning('Client Error: could not fetch the details for account %s.', account.label)
            raise
        except BrowserHTTPNotFound:
            # Some accounts return 404 with an error message on the website
            self.logger.warning('404 Error: could not fetch the details for account %s.', account.label)
        else:
            return True

    @retry(ReadTimeout)
    def go_to_account_space(self):
        self.accounts.stay_or_go()

    @need_login
    def iter_accounts(self):
        try:
            self.go_to_account_space()
        except BrowserHTTPError:
            raise BrowserUnavailable()

        if not self.page.has_accounts():
            self.logger.warning('Could not find any account')
            return

        bank_accounts = self.page.iter_bank_accounts()
        wealth_accounts = self.page.iter_wealth_accounts()

        for account in bank_accounts:
            self.go_to_account(account)
            account._is_market_account = self.page.is_market_account()
            yield account

        for account in wealth_accounts:
            # The new API with account details is only available for bank accounts.
            # We still use the old version until savings accounts are migrated to the new API.
            if not self.go_to_account(account):
                # For some accounts, the details URL systematically leads to an error.
                # We do not fetch them.
                continue
            if self.account_vie_euro.is_here() and self.page.is_error():
                # Sometimes the account URL works but it lands on a page with a status and error message.
                # The account has no balance and no info on the website, we do not fetch it.
                continue
            if any((
                self.account_detail.is_here(),
                self.account_vie_euro.is_here(),
                self.account_vie_ucco.is_here(),
                self.account_vie_uc.is_here(),
            )):
                self.page.fill_account(obj=account)
                if account.type == Account.TYPE_UNKNOWN:
                    if not empty(account._fiscality_type):
                        # Type account using fiscality if the label could not type the account properly
                        account.type = account._fiscality_type
                    else:
                        self.logger.warning('Could not type account "%s"', account.label)

                if account.type == Account.TYPE_PER:
                    # Transform account into PER and set PER version
                    per = Per.from_dict(account.to_dict())

                    per._fiscality_type = account._fiscality_type
                    per._profile_types = account._profile_types
                    per._history_urls = account._history_urls
                    per._is_bank_account = account._is_bank_account
                    per._is_market_account = account._is_market_account

                    if 'PER INDIVIDUEL' in per.label.upper():
                        per.version = PerVersion.PERIN
                    elif 'PER ENTREPRISE' in per.label.upper():
                        per.version = PerVersion.PERCOL

                    # No information concerning the PER provider_type
                    per.provider_type = NotAvailable
                    yield per

                else:
                    yield account

    @need_login
    def get_profile(self):
        self.profile.stay_or_go()
        return self.page.get_profile()

    def create_euro_fund(self, account):
        inv = Investment()
        inv.label = 'FONDS EN EUROS'
        inv.valuation = account.balance
        inv.code = NotAvailable
        inv.code_type = NotAvailable
        return inv

    @need_login
    def iter_investment(self, account):
        if account.balance == 0:
            return

        if self.bank_account_detail.match(account.url):
            self.location(account.url)
            if account._is_market_account:
                for inv in self.page.iter_investment():
                    yield inv
        elif not account._profile_types:
            if not account.url:
                raise NotImplementedError()
            if self.account_vie_euro.match(account.url):
                yield self.create_euro_fund(account)
            else:
                try:
                    self.location(account.url)
                    for inv in self.page.iter_investment():
                        yield inv
                except BrowserHTTPError:
                    yield self.create_euro_fund(account)
                # No invest on this account
                except BrowserHTTPNotFound as e:
                    self.logger.warning(e)
        else:
            for profile_type in account._profile_types:
                try:
                    self.account_detail.go(id=account.number, profile_type=profile_type)
                except ClientError as e:
                    # Some accounts return 403 forbidden and don't appear on the website
                    if e.response.status_code == 403:
                        self.logger.warning('Client Error: could not fetch investments for account %s.', account.label)
                        continue
                    else:
                        raise
                for inv in self.page.iter_investment():
                    inv._profile_type = profile_type
                    yield inv

    @need_login
    def iter_pocket(self, account):
        if not account._profile_types:
            raise NotImplementedError()

        # not the best way but those names are generated with js
        natures = {
            'UC': 'Unités de compte',
            'DV': 'Fonds en Euros',
        }
        profiles = {
            'AP': 'sous allocation pilotée',
            'LIBRE': 'sous allocation libre'
        }

        pockets = []
        # for now, we create a pocket for each investment
        for inv in self.iter_investment(account):
            pocket = Pocket()
            nature = natures.get(inv._nature)
            if nature:
                pocket.label = ('%s %s' % (nature, profiles.get(inv._profile_type, ""))).strip()
            pocket.amount = inv.valuation
            pocket.quantity = inv.quantity
            pocket.availability_date = NotAvailable
            pocket.condition = Pocket.CONDITION_AVAILABLE
            pocket.investment = inv
            pockets.append(pocket)
        return pockets

    @need_login
    def iter_history(self, account):
        if account._is_bank_account:
            # We must do the pagination manually with the URL.
            # There is no indication that we are on the last page except if there are less transactions than the page size.
            # If the total number of transactions is a multiple of the size, we arrive at a page with no transaction.
            # This last page format is different (no operations list at all).
            index = 0
            size = 50
            has_next_page = True
            iteration = 0
            while has_next_page and iteration < 100:
                iteration += 1
                self.bank_account_transactions.go(account_id=account.id, index=index, size=size)
                has_next_page = self.page.has_next_page(size)
                index += size
                if self.page.has_operations():
                    for tr in self.page.iter_history():
                        yield tr
        elif account._history_urls:
            for urls in account._history_urls:
                try:
                    self.location(urls)
                except (ConnectionError, ServerError) as e:
                    # Error on swisslife website.
                    self.logger.error(e)
                for tr in self.page.iter_history():
                    yield tr
        elif not account.url:
            raise NotImplementedError()
        # Article 39 accounts history
        elif 'contratVieucEntreprise' in account.url:
            # This key param seems to be hardcoded for this type of contract
            params = {'natureCodes': 'A02A,A02B,A02D,A02T,B03A,B03C,B03I,B03R,B03S,B03T,C06A,C06J,C06L,C06M,C06S,C06P,C06B'}
            self.location('/api/v3/contratVieucEntreprise/operations/%s' % account.id, params=params)
            for tr in sorted_transactions(self.page.iter_history()):
                yield tr
        elif 'contratVieEuro' in account.url:
            # If there are no transactions, the request will fail
            try:
                self.location(account.url + '/primesPayees')
            except (BrowserHTTPError, BrowserHTTPNotFound):
                self.logger.warning('Could not access history for account %s', account.id)
            else:
                for tr in sorted_transactions(self.page.iter_history()):
                    yield tr
        else:
            self.location(account.url)
            for tr in sorted_transactions(self.page.iter_history()):
                yield tr
