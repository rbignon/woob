# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
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

import datetime
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from requests.exceptions import ConnectionError

from woob.browser import URL, need_login
from woob.browser.mfa import TwoFactorBrowser
from woob.browser.exceptions import (
    BrowserTooManyRequests, ClientError, ServerError,
)
from woob.exceptions import (
    ActionNeeded, ActionType, BrowserIncorrectPassword, BrowserPasswordExpired,
    OfflineOTPQuestion,
)
from woob.tools.capabilities.bank.investments import create_french_liquidity
from woob.capabilities.base import Currency, empty
from woob.capabilities.bank import Account
from woob.tools.decorators import retry

from .pages import (
    LoginPage, OtpPage, AccountsPage, AccountDetailsPage,
    InvestmentPage, HistoryPage, MarketOrdersPage,
    ExchangesPage,
)


class URLWithDate(URL):
    def go(self, fromDate, toDate=None, *args, **kwargs):
        toDate_ = toDate or datetime.datetime.now().strftime('%d/%m/%Y')
        return super(URLWithDate, self).go(
            toDate=toDate_,
            fromDate=fromDate,
            account_id=self.browser.int_account,
            session_id=self.browser.session_id,
        )


class DegiroBrowser(TwoFactorBrowser):
    BASEURL = 'https://trader.degiro.nl'

    TIMEOUT = 60  # Market orders queries can take a long time
    HAS_CREDENTIALS_ONLY = True

    login = URL(r'/login/secure/login', LoginPage)
    send_otp = URL(r'/login/secure/login/totp', OtpPage)
    client = URL(r'/pa/secure/client\?sessionId=(?P<session_id>.*)', LoginPage)
    product = URL(r'/product_search/secure/v5/products/info\?sessionId=(?P<session_id>.*)', InvestmentPage)
    exchanges = URL(r'/product_search/config/dictionary/', ExchangesPage)
    accounts = URL(
        r'/trading(?P<staging>\w*)/secure/v5/update/(?P<account_id>.*);jsessionid=(?P<session_id>.*)\?historicalOrders=0' +
        r'&orders=0&portfolio=0&totalPortfolio=0&transactions=0&alerts=0&cashFunds=0&currencyExchange=0&',
        AccountsPage
    )
    account_details = URL(
        r'https://trader.degiro.nl/trading(?P<staging>\w*)/secure/v5/account/info/(?P<account_id>.*);jsessionid=(?P<session_id>.*)',
        AccountDetailsPage
    )
    transaction_investments = URLWithDate(
        r'/reporting/secure/v4/transactions\?fromDate=(?P<fromDate>.*)' +
        '&groupTransactionsByOrder=false&intAccount=(?P<account_id>.*)' +
        '&orderId=&product=&sessionId=(?P<session_id>.*)' +
        '&toDate=(?P<toDate>.*)',
        HistoryPage
    )
    history = URLWithDate(
        r'/reporting/secure/v4/accountoverview\?fromDate=(?P<fromDate>.*)' +
        '&groupTransactionsByOrder=false&intAccount=(?P<account_id>.*)' +
        '&orderId=&product=&sessionId=(?P<session_id>.*)&toDate=(?P<toDate>.*)',
        HistoryPage
    )
    market_orders = URLWithDate(
        r'/reporting/secure/v4/order-history\?fromDate=(?P<fromDate>.*)' +
        '&toDate=(?P<toDate>.*)&intAccount=(?P<account_id>.*)&sessionId=(?P<session_id>.*)',
        MarketOrdersPage
    )

    __states__ = ('staging', 'session_id', 'int_account', 'name')

    def __init__(self, config, *args, **kwargs):
        super(DegiroBrowser, self).__init__(config, *args, **kwargs)

        self.staging = None
        self.int_account = None
        self.name = None
        self.session_id = None
        self.account = None
        self.invs = {}
        self.trs = {}
        self.products = {}
        self.stock_market_exchanges = {}

        self.AUTHENTICATION_METHODS = {
            'otp': self.handle_otp,
        }

    def locate_browser(self, state):
        # We must check 'staging' state is set before trying to go on AccountsPage.
        if not state.get('staging'):
            if 'staging' in self.session_id:
                self.staging = '_s'
            else:
                self.staging = ''

        try:
            # We try reloading the session with the previous states if they are not expired.
            # If they are, we encounter a ClientError 401 Unauthorized, we need to relogin.
            self.accounts.go(staging=self.staging, account_id=self.int_account, session_id=self.session_id)
        except ClientError as e:
            if e.response.status_code != 401:
                raise

    @retry(BrowserTooManyRequests, delay=30)
    def init_login(self):
        try:
            self.login.go(json={'username': self.username, 'password': self.password})
        except ClientError as e:
            if e.response.status_code == 400:
                raise BrowserIncorrectPassword()
            elif e.response.status_code == 403:
                status = e.response.json().get('statusText', '')
                if status == 'accountBlocked':
                    raise BrowserIncorrectPassword('Your credentials are invalid and your account is currently blocked.')
                raise Exception('Login failed with status: "%s".', status)
            elif e.response.status_code == 412:
                status = e.response.json().get('statusText')
                # https://trader.degiro.nl/translations/?language=fr&country=FR&modules=commonFE%2CloginFE
                # for status_messages

                if status == 'jointAccountPersonNeeded':
                    # After the first post in a joint account, we get a json containing IDs of
                    # the account holders. Then we need to make a second post to send the
                    # ID of the user trying to log in.
                    persons = e.response.json().get('persons')
                    if not persons:
                        raise AssertionError('No profiles to select from')
                    self.login.go(json={
                        'password': self.password,
                        'personId': persons[0]['id'],
                        'username': self.username,
                    })
                elif status == 'passwordReset':
                    raise BrowserPasswordExpired("Un e-mail vous a été envoyé afin de réinitialiser votre mot de passe. Veuillez consulter votre boite de réception. Si vous n’êtes pas à l’origine de cette demande, merci de contacter notre service clients.")
                elif status:
                    raise AssertionError('Unhandled status: %s' % status)
                else:
                    raise
            elif e.response.status_code == 429:
                # We sometimes get an HTTP 429 status code when logging in,
                # with no other information than 'Too Many Requests'.
                # We want to try again in this case.
                raise BrowserTooManyRequests()
            else:
                raise

        # if 2FA is required for this user
        if self.page.has_2fa():
            self.check_interactive()

            # An authenticator is used here, so no notification or SMS,
            # we use the same message as on the website.
            raise OfflineOTPQuestion(
                'otp',
                message='Enter your confirmation code',
            )
        else:
            self.finalize_login()

    def handle_otp(self):
        data = {
            'oneTimePassword': self.config['otp'].get(),
            'password': self.password,
            'queryParams': {
                'redirectUrl': 'https://trader.degiro.nl/trader/#/markets?enabledLanguageCodes=fr&hasPortfolio=false&favouritesListsIds='
            },
            'username': self.username.lower(),
        }

        try:
            self.send_otp.go(json=data)
        except ClientError as e:
            json_err = e.response.json().get('statusText')
            if e.response.status_code == 400 and json_err == 'badCredentials':
                raise BrowserIncorrectPassword('The confirmation code is incorrect', bad_fields=['otp'])
            raise

        self.finalize_login()

    def finalize_login(self):
        self.session_id = self.page.get_session_id()
        if not self.session_id:
            raise AssertionError(
                'Missing a session identifier when finalizing the login.',
            )

        self.staging = ''
        if 'staging' in self.session_id:
            self.staging = '_s'

        self.client.go(session_id=self.session_id)

        self.int_account = self.page.get_information('intAccount')
        self.name = self.page.get_information('displayName')

        if self.int_account is None:
            # For various ActionNeeded, field intAccount is not present in the json.
            raise ActionNeeded(
                locale="fr-FR", message="Merci de compléter votre profil sur le site de Degiro",
                action_type=ActionType.FILL_KYC,
            )

    def fill_stock_market_exchanges(self):
        if not self.stock_market_exchanges:
            self.exchanges.go()
            self.stock_market_exchanges = self.page.get_stock_market_exchanges()

    @need_login
    def iter_accounts(self):
        if self.account is None:
            self.accounts.go(staging=self.staging, account_id=self.int_account, session_id=self.session_id)
            self.account = self.page.get_account()
            # Go to account details to fetch the right currency
            try:
                self.account_details.go(staging=self.staging, account_id=self.int_account, session_id=self.session_id)
            except ClientError as e:
                if e.response.status_code == 412:
                    # No useful message on the API response. On the website, there is a form to complete after login.
                    raise ActionNeeded(
                        locale="fr-FR", message="Merci de compléter votre profil sur le site de Degiro",
                        action_type=ActionType.FILL_KYC,
                    )
                raise
            self.account.currency = self.page.get_currency()
            # Account balance is the sum of investments valuations
            self.account.balance = sum(inv.valuation.quantize(Decimal('0.00')) for inv in self.iter_investment(self.account))
        yield self.account

    @need_login
    def iter_investment(self, account):
        self.fill_stock_market_exchanges()

        if account.id not in self.invs:
            self.accounts.stay_or_go(staging=self.staging, account_id=self.int_account, session_id=self.session_id)
            raw_invests = list(self.page.iter_investment(currency=account.currency, exchanges=self.stock_market_exchanges))
            # Some invests are present twice. We need to combine them into one, as it's done on the website.
            invests = {}
            for raw_inv in raw_invests:
                if raw_inv.label not in invests:
                    invests[raw_inv.label] = raw_inv
                else:
                    invests[raw_inv.label].quantity += raw_inv.quantity
                    invests[raw_inv.label].valuation += raw_inv.valuation

        for inv in invests.values():
            # Replace as liquidities investments that are cash
            if len(inv.label) < 4 and Currency.get_currency(inv.label):
                yield create_french_liquidity(inv.valuation)
            # Since we are adding Buy/sell positions of the investments
            # We need to filter out investments with a quantity sum equal to 0
            # those investments are considered as "closed" on the website
            elif empty(inv.quantity) or inv.quantity:
                yield inv

    @need_login
    def fetch_market_orders(self, from_date, to_date):
        self.fill_stock_market_exchanges()

        market_orders = []
        self.market_orders.go(fromDate=from_date.strftime('%d/%m/%Y'), toDate=to_date.strftime('%d/%m/%Y'))
        # Market orders are displayed chronogically so we must reverse them
        for market_order in sorted(
            self.page.iter_market_orders(exchanges=self.stock_market_exchanges),
            reverse=True,
            key=lambda order: order.date
        ):
            market_orders.append(market_order)

        return market_orders

    @need_login
    def iter_market_orders(self, account):
        if account.type not in (Account.TYPE_MARKET, Account.TYPE_PEA):
            return

        # We can fetch up to 3 months of history (minus one day), older than that the JSON response is empty
        # We must fetch market orders 2 weeks at a time because if we fetch too many orders at a time the API crashes
        market_orders = []
        to_date = datetime.datetime.now()
        oldest = (to_date - relativedelta(months=3) + relativedelta(days=1))
        step = relativedelta(weeks=2)
        from_date = (to_date - step)

        while to_date > oldest:
            try:
                market_orders.extend(self.fetch_market_orders(from_date, to_date))
            except (ConnectionError, ServerError):
                # Fetching market orders can be impossible within the timeout limit because of there are too many.
                # Since we can't fetch 3 months of available market order history with a 2-weeks step,
                # we will fetch 2 weeks market order history (by editing 'oldest') and set the 'step' to 2 days.
                # That way, we will still fetch recent orders within a reasonable amount of time and prevent any crash.
                oldest = (to_date - relativedelta(weeks=2) + relativedelta(days=1))
                step = relativedelta(days=2)
                from_date = (to_date - step)
                market_orders.extend(self.fetch_market_orders(from_date, to_date))

            to_date = from_date - relativedelta(days=1)
            from_date = max(
                oldest,
                to_date - step,
            )

        return market_orders

    @need_login
    def iter_history(self, account):
        if account.id not in self.trs:
            fromDate = (datetime.datetime.now() - relativedelta(years=1)).strftime('%d/%m/%Y')

            self.transaction_investments.go(fromDate=fromDate)

            self.fetch_products(list(self.page.get_products()))

            transaction_investments = list(self.page.iter_transaction_investments())
            self.history.go(fromDate=fromDate)

            # the list can be pretty big, and the tr list too
            # avoid doing O(n*n) operation
            trinv_dict = {(inv.code, inv._action, inv._datetime): inv for inv in transaction_investments}

            trs = list(self.page.iter_history(transaction_investments=NoCopy(trinv_dict), account_currency=account.currency))
            self.trs[account.id] = trs
        return self.trs[account.id]

    # We can encounter random 502 (Bad Gateway), retrying fixes the issue.
    @retry(ServerError)
    def fetch_products(self, ids):
        ids = list(set(ids) - set(self.products.keys()))
        if ids:
            page = self.product.open(
                json=ids,
                session_id=self.session_id,
            )
            self.products.update(page.get_products())

    # We can encounter random 502 (Bad Gateway), retrying fixes the issue.
    @retry(ServerError)
    def get_product(self, id):
        if id not in self.products:
            self.fetch_products([id])
        return self.products[id]


class NoCopy(object):
    # params passed to a @method are deepcopied, in each iteration of ItemElement
    # so we want to avoid repeatedly copying objects since we don't intend to modify them

    def __init__(self, v):
        self.v = v

    def __deepcopy__(self, memo):
        return self
