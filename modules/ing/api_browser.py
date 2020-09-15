# -*- coding: utf-8 -*-

# Copyright(C) 2019 Sylvie Ye
#
# This file is part of weboob.
#
# weboob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# weboob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with weboob. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

from __future__ import unicode_literals

from collections import OrderedDict, Counter
from functools import wraps
import re

from weboob.browser import LoginBrowser, URL, StatesMixin, need_login
from weboob.exceptions import BrowserIncorrectPassword, ActionNeeded, AuthMethodNotImplemented
from weboob.browser.exceptions import ClientError, ServerError
from weboob.capabilities.bank import (
    Account, TransferBankError, TransferInvalidAmount,
    AddRecipientStep, RecipientInvalidOTP,
    AddRecipientTimeout, AddRecipientBankError, RecipientInvalidIban,
)
from weboob.capabilities.bill import Subscription
from weboob.tools.capabilities.bank.transactions import FrenchTransaction
from weboob.tools.value import Value

from .api import (
    LoginPage, AccountsPage, HistoryPage, ComingPage, AccountInfoPage,
    DebitAccountsPage, CreditAccountsPage, TransferPage,
    ProfilePage, LifeInsurancePage, InvestTokenPage,
    AddRecipientPage, OtpChannelsPage, ConfirmOtpPage,
)
from .api.accounts_page import RedirectOldPage, BourseLandingPage
from .api.profile_page import UselessProfilePage
from .api.login import StopPage, ActionNeededPage
from .api.documents import StatementsPage
from .boursedirect_browser import BourseDirectBrowser


def start_with_main_site(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        self.go_main_site()
        assert 'm.ing.fr' in self.url
        return func(self, *args, **kwargs)

    return wrapper


class IngAPIBrowser(LoginBrowser, StatesMixin):
    BASEURL = 'https://m.ing.fr'
    STATE_DURATION = 10

    # Login
    context = URL(r'/secure/api-v1/session/context')
    login = URL(r'/secure/api-v1/login/cif', LoginPage)
    keypad = URL(r'/secure/api-v1/login/keypad', LoginPage)
    pin_page = URL(r'/secure/api-v1/login/sca/pin', LoginPage)

    # Error on old website
    errorpage = URL(r'https://secure.ing.fr/.*displayCoordonneesCommand.*', StopPage)
    actioneeded = URL(
        r'https://secure.ing.fr/general\?command=displayTRAlertMessage',
        r'https://secure.ing.fr/protected/pages/common/eco1/moveMoneyForbidden.jsf',
        ActionNeededPage
    )

    # bank
    history = URL(
        r'/secure/api-v1/accounts/(?P<account_uid>.*)/transactions/after/(?P<tr_id>\d+)/limit/50',
        HistoryPage
    )
    coming = URL(r'/secure/api-v1/accounts/(?P<account_uid>.*)/futureOperations', ComingPage)
    account_info = URL(r'/secure/api-v1/accounts/(?P<account_uid>[^/]+)/bankRecord', AccountInfoPage)
    accounts = URL(r'/secure/api-v1/accounts$', AccountsPage)

    # wealth
    api_to_bourse = URL(r'/saveinvestapi/v1/bourse/redirect/uid/(?P<account_uid>.+)')
    invest_token_page = URL(r'/secure/api-v1/saveInvest/token/generate', InvestTokenPage)
    life_insurance = URL(r'/saveinvestapi/v1/lifeinsurance/contract/(?P<account_uid>)', LifeInsurancePage)
    bourse_to_api = URL(r'https://bourse.ing.fr/priv/redirectIng.php\?pageIng=INFO')
    redirect_old = URL(r'https://secure.ing.fr/general\?command=goToCDDCommand', RedirectOldPage)
    bourse_landing = URL(r'https://bourse.ing.fr/fr/page/portefeuille', BourseLandingPage)

    # transfer
    credit_accounts = URL(
        r'/secure/api-v1/transfers/debitAccounts/(?P<account_uid>.*)/creditAccounts',
        CreditAccountsPage
    )
    debit_accounts = URL(r'/secure/api-v1/transfers/debitAccounts', DebitAccountsPage)
    init_transfer_page = URL(r'/secure/api-v1/transfers/v2/new/validate', TransferPage)
    exec_transfer_page = URL(r'/secure/api-v1/transfers/v2/new/execute/pin', TransferPage)

    # recipient
    add_recipient = URL(r'secure/api-v1/externalAccounts/add/validateRequest', AddRecipientPage)
    otp_channels = URL(r'secure/api-v1/sensitiveoperation/ADD_TRANSFER_BENEFICIARY/otpChannels', OtpChannelsPage)
    confirm_otp = URL(r'secure/api-v1/sca/confirmOtp', ConfirmOtpPage)

    # profile
    informations = URL(r'/secure/api-v1/customer/info', ProfilePage)
    useless_profile = URL(r'/secure/personal-data/information', UselessProfilePage)

    # document
    statements = URL(r'/secure/api-v1/accounts/statement/metadata/(?P<account_uid>.+)', StatementsPage)
    statement_dl = URL(r'/secure/api-v1/accounts/statement/bank/(?P<account_uid>.+)/(?P<year>\d+)/(?P<month>\d+)')

    __states__ = ('need_reload_state', 'add_recipient_info')

    def __init__(self, *args, **kwargs):
        self.birthday = kwargs.pop('birthday')
        super(IngAPIBrowser, self).__init__(*args, **kwargs)

        dirname = self.responses_dirname
        if dirname:
            dirname += '/bourse'
        kwargs['responses_dirname'] = dirname
        self.bourse = BourseDirectBrowser(None, None, **kwargs)

        self.transfer_data = None
        self.need_reload_state = None
        self.add_recipient_info = None
        self.invest_token = None

    def load_state(self, state):
        # reload state only for new recipient
        if state.get('need_reload_state'):
            state.pop('url', None)
            self.need_reload_state = None
            super(IngAPIBrowser, self).load_state(state)

    WRONGPASS_CODES = (
        'AUTHENTICATION.INVALID_PIN_CODE',
        'AUTHENTICATION.INVALID_CIF_AND_BIRTHDATE_COMBINATION',
        'AUTHENTICATION.FIRST_WRONG_PIN_ATTEMPT',
        'AUTHENTICATION.SECOND_WRONG_PIN_ATTEMPT',
        'AUTHENTICATION.CUSTOMER_DECEASED',
        'SCA.WRONG_AUTHENTICATION',
    )

    ACTIONNEEDED_CODES = (
        'AUTHENTICATION.ACCOUNT_INACTIVE',
        'AUTHENTICATION.ACCOUNT_LOCKED',
        'AUTHENTICATION.NO_COMPLETE_ACCOUNT_FOUND',
        'SCA.ACCOUNT_LOCKED',
    )

    def handle_login_error(self, r):
        error_page = r.response.json()
        assert 'error' in error_page, "Something went wrong in login"
        error = error_page['error']

        if error['code'] in self.WRONGPASS_CODES:
            raise BrowserIncorrectPassword(error['message'])
        elif error['code'] in self.ACTIONNEEDED_CODES:
            raise ActionNeeded(error['message'])

        raise Exception("%r code isn't handled yet: %s" % (error['code'], error['message']))

    def do_login(self):
        if not self.password.isdigit():
            raise BrowserIncorrectPassword()

        # login on new website
        # update cookies
        self.context.go()

        data = OrderedDict([
            ('birthDate', self.birthday.strftime('%d%m%Y')),
            ('cif', self.username),
        ])
        try:
            self.login.go(json=data)
        except ClientError as e:
            self.handle_login_error(e)

        data = '{"keyPadSize":{"width":3800,"height":1520},"mode":""}'
        self.keypad.go(data=data, headers={'Content-Type': 'application/json'})

        keypad_url = self.page.get_keypad_url()
        img = self.open('/secure/api-v1%s' % keypad_url).content
        data = {
            'clickPositions': self.page.get_password_coord(img, self.password),
        }

        try:
            self.pin_page.go(json=data, headers={'Referer': self.pin_page.build()})
        except ClientError as e:
            self.handle_login_error(e)

        if not self.page.has_strong_authentication():
            self.auth_token = self.page.response.headers['Ingdf-Auth-Token']
            self.session.headers['Ingdf-Auth-Token'] = self.auth_token
            self.session.cookies.set('ingdfAuthToken', self.auth_token, domain='m.ing.fr')
        else:
            raise ActionNeeded("Vous devez réaliser la double authentification sur le portail internet")

        # to be on logged page, to avoid relogin
        self.accounts.go()

    def deinit(self):
        self.bourse.deinit()
        super(IngAPIBrowser, self).deinit()

    ############# CapBank #############
    def get_invest_token(self):
        if not self.invest_token:
            self.go_main_site()
            self.invest_token_page.go()
            self.invest_token = self.page.get_invest_token()

        return self.invest_token

    types_with_iban = (
        Account.TYPE_CHECKING,
        Account.TYPE_SAVINGS,
        Account.TYPE_MARKET,
        Account.TYPE_PEA,
    )

    @start_with_main_site
    def get_api_accounts(self):
        self.accounts.stay_or_go()
        return self.page.iter_accounts()

    @need_login
    def iter_accounts(self):
        api_accounts = list(self.get_api_accounts())
        dups_detection = Counter(account.number for account in api_accounts)
        for number, qty in dups_detection.items():
            if qty > 1:
                self.logger.error('account number %r is present %r times', number, qty)
        api_by_number = {acc.number[-4:]: acc for acc in api_accounts}

        for account in api_accounts:
            self.fill_account_iban(account)

            # We get life insurance details from the API, not the old website
            # If the balance is 0, the details page throws an error 500
            if account.type == Account.TYPE_LIFE_INSURANCE:
                if account.balance != 0:
                    # Prefer do an open() NOT to set the life insurance url as next Referer.
                    # If the Referer doesn't point to /secure, the site might do error 500...
                    page = self.life_insurance.open(
                        account_uid=account._uid,
                        headers={
                            'Authorization': 'Bearer %s' % self.get_invest_token(),
                        }
                    )
                    page.fill_account(obj=account)

        # one single pass for boursedirect accounts, avoid moving back-and-forth
        for account in api_accounts:
            if account.type not in (Account.TYPE_PEA, Account.TYPE_MARKET):
                continue

            self.go_bourse(account)
            bourse_accounts = list(self.bourse.iter_accounts_but_insurances())

            for bourse_account in bourse_accounts:
                # bourse number is in format 111TI11111119999EUR
                # where XXXX9999 is the corresponding API account number
                common = re.search(r'(\d{4})[A-Z]{3}$', bourse_account.number).group(1)
                account = api_by_number[common]
                account.balance = bourse_account.balance  # fresher balance
                account._bourse_id = bourse_account.id
                account._select = bourse_account._select  # used by boursedirect browser

            break

        return api_accounts

    @start_with_main_site
    def get_api_history(self, account):
        # first request transaction id is 0 to get the most recent transaction
        first_transaction_id = 0
        request_number_security = 0

        while request_number_security < 200:
            request_number_security += 1

            # first_transaction_id is 0 for the first request, then
            # it will decreasing after first_transaction_id become the last transaction id of the list
            self.history.go(account_uid=account._uid, tr_id=first_transaction_id)
            if self.page.is_empty_page():
                # empty page means that there are no more transactions
                break

            for tr in self.page.iter_history():
                # transaction id is decreasing
                first_transaction_id = int(tr._web_id)
                if tr.type == FrenchTransaction.TYPE_CARD:
                    tr.bdate = tr.rdate
                yield tr

            # like website, add 1 to the last transaction id of the list to get next transactions page
            first_transaction_id += 1

    history_account_types = (
        Account.TYPE_CHECKING,
        Account.TYPE_SAVINGS,
        Account.TYPE_LIFE_INSURANCE,
    )

    @need_login
    def iter_history(self, account):
        if account.type in (Account.TYPE_PEA, Account.TYPE_MARKET):
            self.go_bourse(account)
            return self.bourse.iter_history(account)
        elif account.type not in self.history_account_types:
            raise NotImplementedError()
        else:
            if account.type == account.TYPE_LIFE_INSURANCE and account.balance == 0:
                # Details page throws an error 500
                return []
            return self.get_api_history(account)

    @need_login
    def iter_coming(self, account):
        if account.type not in self.history_account_types:
            raise NotImplementedError()

        self.go_main_site()
        self.coming.go(account_uid=account._uid)
        for tr in self.page.iter_coming():
            if tr.type == FrenchTransaction.TYPE_CARD:
                tr.bdate = tr.rdate
            yield tr

    @need_login
    @start_with_main_site
    def fill_account_coming(self, account):
        self.coming.go(account_uid=account._uid)
        self.page.fill_account_coming(obj=account)

    @need_login
    def fill_account_iban(self, account):
        if account.type in self.types_with_iban:
            self.go_main_site()  # no need to do it if there's no iban
            self.account_info.go(account_uid=account._uid)
            account.iban = self.page.get_iban()

    @need_login
    def go_bourse(self, account):
        if 'bourse.ing.fr' in self.url:
            self.logger.debug('already on bourse site')
            return

        assert account.type in (Account.TYPE_PEA, Account.TYPE_MARKET)

        self.logger.debug('going to bourse site')
        self.api_to_bourse.go(
            account_uid=account._uid,
            headers={'Authorization': 'Bearer %s' % self.get_invest_token()}
        )
        bourse_url = self.response.json()['url']

        self.location(bourse_url, data='')

        self.bourse.session.cookies.update(self.session.cookies)
        self.bourse.location(self.url)

    @need_login
    def go_main_site(self):
        if 'm.ing.fr' in self.url:
            self.logger.debug('already on main site')
            return

        self.logger.debug('going to main site')
        if 'bourse.ing.fr' in self.url:
            try:
                self.bourse_to_api.go()
            except ServerError:
                self.logger.debug('bourse_to_api failed...')
                # this is an absolute clusterfuck
                self.location(self.absurl('/secure', base=True))
                self.accounts.go()
            else:
                self.logger.info('bourse_to_api did work, hurray!')

    ############# CapWealth #############
    @need_login
    def get_investments(self, account):
        if account.type not in (account.TYPE_MARKET, account.TYPE_LIFE_INSURANCE, account.TYPE_PEA):
            return []

        if account.type == account.TYPE_LIFE_INSURANCE:
            if account.balance == 0:
                # Details page throws an error 500
                return []

            self.go_main_site()
            page = self.life_insurance.open(
                account_uid=account._uid, headers={
                    'Authorization': 'Bearer %s' % self.get_invest_token(),
                }
            )
            return page.iter_investments()

        self.go_bourse(account)
        return self.bourse.iter_investment(account)

    @need_login
    def iter_market_orders(self, account):
        if account.type not in (account.TYPE_MARKET, account.TYPE_PEA):
            return []

        self.go_bourse(account)
        return self.bourse.iter_market_orders(account)

    ############# CapTransferAddRecipient #############
    @need_login
    @start_with_main_site
    def iter_recipients(self, account):
        self.debit_accounts.go()
        if account._uid not in self.page.get_debit_accounts_uid():
            return

        self.credit_accounts.go(account_uid=account._uid)
        for recipient in self.page.iter_recipients(acc_uid=account._uid):
            yield recipient

    def handle_transfer_errors(self, r):
        error_page = r.response.json()
        assert 'error' in error_page, "Something went wrong, transfer is not created"

        error = error_page['error']
        error_msg = error['message']

        if error['code'] == 'TRANSFER.INVALID_AMOUNT_MINIMUM':
            raise TransferInvalidAmount(message=error_msg)
        elif error['code'] == 'INPUT_INVALID' and len(error['values']):
            for value in error['values']:
                error_msg = '%s %s %s.' % (error_msg, value, error['values'][value])

        raise TransferBankError(message=error_msg)

    @need_login
    @start_with_main_site
    def init_transfer(self, account, recipient, transfer):
        data = {
            'amount': transfer.amount,
            'executionDate': transfer.exec_date.strftime('%Y-%m-%d'),
            'keyPadSize': {'width': 3800, 'height': 1520},
            'label': transfer.label,
            'fromAccount': account._uid,
            'toAccount': recipient.id,
        }
        try:
            self.init_transfer_page.go(json=data, headers={'Referer': self.absurl('/secure/transfers/new')})
        except ClientError as e:
            self.handle_transfer_errors(e)

        if self.page.is_otp_authentication():
            raise AuthMethodNotImplemented()

        suggested_date = self.page.suggested_date
        if transfer.exec_date and transfer.exec_date < suggested_date:
            transfer.exec_date = suggested_date
        assert suggested_date == transfer.exec_date, "Transfer date is not valid"

        self.transfer_data = data
        self.transfer_data.pop('keyPadSize')
        self.transfer_data['clickPositions'] = self.page.get_password_coord(self.password)

        return transfer

    @need_login
    @start_with_main_site
    def execute_transfer(self, transfer):
        headers = {
            'Referer': self.absurl('/secure/transfers/new'),
            'Accept': 'application/json, text/plain, */*',
        }
        self.exec_transfer_page.go(json=self.transfer_data, headers=headers)

        assert self.page.transfer_is_validated, "Transfer is not validated"
        return transfer

    @need_login
    def send_sms_to_user(self, recipient, sms_info):
        """Add recipient with OTP SMS authentication"""
        data = {
            'channelType': sms_info['type'],
            'externalAccountsRequest': self.add_recipient_info,
            'sensitiveOperationAction': 'ADD_TRANSFER_BENEFICIARY',
        }

        phone_id = sms_info['phone']
        data['channelValue'] = phone_id
        self.add_recipient_info['phoneUid'] = phone_id

        self.location(self.absurl('/secure/api-v1/sca/sendOtp', base=True), json=data)
        self.need_reload_state = True
        raise AddRecipientStep(recipient, Value('code', label='Veuillez saisir le code temporaire envoyé par SMS'))

    def handle_recipient_error(self, r):
        # The bank gives an error message when an error occures.
        # But sometimes the message is not relevant.
        # So I may replace it by nothing or by a custom message.
        # The exception to raise can be coupled with:
        # * Nothing: empty message
        # * None: message of the bank
        # * String: custom message
        RECIPIENT_ERROR = {
            'SENSITIVE_OPERATION.SENSITIVE_OPERATION_NOT_FOUND': (AddRecipientTimeout,),
            'SENSITIVE_OPERATION.EXPIRED_TEMPORARY_CODE': (AddRecipientTimeout, None),
            'EXTERNAL_ACCOUNT.EXTERNAL_ACCOUNT_ALREADY_EXISTS': (AddRecipientBankError, None),
            'EXTERNAL_ACCOUNT.ACCOUNT_RESTRICTION': (AddRecipientBankError, None),
            'EXTERNAL_ACCOUNT.EXTERNAL_ACCOUNT_IS_INTERNAL_ACCOUT': (AddRecipientBankError, None),  # nice spelling
            'EXTERNAL_ACCOUNT.IBAN_NOT_FRENCH': (RecipientInvalidIban, "L'IBAN doit correpondre à celui d'une banque domiciliée en France."),
            'SCA.WRONG_OTP_ATTEMPT': (RecipientInvalidOTP, None),
            'INPUT_INVALID': (AssertionError, None),  # invalid request
        }

        error_page = r.response.json()
        if 'error' in error_page:
            error = error_page['error']

            error_exception = RECIPIENT_ERROR.get(error['code'])
            if error_exception:
                if len(error_exception) == 1:
                    raise error_exception[0]()
                elif error_exception[1] is None:
                    raise error_exception[0](message=error['message'])
                else:
                    raise error_exception[0](message=error_exception[1])

            raise AssertionError('Recipient error "%s" not handled' % error['code'])

    @need_login
    def end_sms_recipient(self, recipient, code):
        # create a variable to empty the add_recipient_info
        # so that if there is a problem it will not be caught
        # in the StatesMixin
        rcpt_info = self.add_recipient_info
        self.add_recipient_info = None

        if not re.match(r'^\d{6}$', code):
            raise RecipientInvalidOTP()

        data = {
            'externalAccountsRequest': rcpt_info,
            'otp': code,
            'sensitiveOperationAction': 'ADD_TRANSFER_BENEFICIARY',
        }

        try:
            self.confirm_otp.go(json=data)
        except ClientError as e:
            self.handle_recipient_error(e)
            raise

    @need_login
    @start_with_main_site
    def new_recipient(self, recipient, **params):
        # sms only, we don't handle the call
        if 'code' in params:
            # part 2 - finalization
            self.end_sms_recipient(recipient, params['code'])

            # WARNING: On the recipient list, the IBAN is masked
            # so I cannot match it
            # The label is not checked by the website
            # so I cannot match it
            return recipient

        # part 1 - initialization
        # Set sign method
        self.otp_channels.go()
        sms_info = self.page.get_sms_info()

        try:
            self.add_recipient.go(json={
                'accountHolderName': recipient.label,
                'iban': recipient.iban,
            })
        except ClientError as e:
            self.handle_recipient_error(e)
            raise

        assert self.page.check_recipient(recipient), "The recipients don't match."
        self.add_recipient_info = self.page.doc

        # WARNING: this send validation request to user
        self.send_sms_to_user(recipient, sms_info)

    @need_login
    @start_with_main_site
    def get_api_emitters(self):
        self.debit_accounts.go()
        return self.page.iter_emitters()

    @need_login
    def iter_emitters(self):
        emitters = list(self.get_api_emitters())
        accounts = {account.id: account for account in self.get_api_accounts()}

        for emitter in emitters:
            account = accounts[emitter.id]
            emitter.balance = account.balance
            emitter.currency = account.currency

        return emitters

    ############# CapDocument #############
    types_with_docs = (
        Account.TYPE_CHECKING,
        Account.TYPE_SAVINGS,
    )

    @need_login
    @start_with_main_site
    def get_subscriptions(self):
        for account in self.get_api_accounts():
            if account.type not in self.types_with_docs:
                continue

            sub = Subscription()
            sub.id = account.id
            sub.label = account.label
            yield sub

    @need_login
    @start_with_main_site
    def get_documents(self, subscription):
        self.statements.go(account_uid=subscription.id)
        return self.page.iter_documents(subscription=subscription.id)

    @need_login
    @start_with_main_site
    def download_document(self, document):
        return self.open(document.url).content

    ############# CapProfile #############
    @need_login
    @start_with_main_site
    def get_profile(self):
        self.informations.go()
        return self.page.get_profile()
