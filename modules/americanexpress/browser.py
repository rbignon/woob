# -*- coding: utf-8 -*-

# Copyright(C) 2013 Romain Bignon
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

from __future__ import unicode_literals

import datetime
import uuid
from dateutil.parser import parse as parse_date
from collections import OrderedDict

from woob.browser.selenium import (
    SeleniumBrowser, SubSeleniumMixin, IsHereCondition, webdriver,
)
from woob.exceptions import (
    BrowserIncorrectPassword, ActionNeeded, BrowserUnavailable,
    AuthMethodNotImplemented, BrowserQuestion, ScrapingBlocked,
)
from woob.browser.browsers import TwoFactorBrowser, need_login
from woob.browser.exceptions import HTTPNotFound, ServerError, ClientError
from woob.browser.url import URL
from woob.tools.compat import urljoin, urlencode, quote
from woob.tools.value import Value

from .pages import (
    AccountsPage, JsonBalances, JsonPeriods, JsonHistory,
    JsonBalances2, CurrencyPage, LoginPage, NoCardPage,
    NotFoundPage, HomeLoginPage,
    ReadAuthChallengePage, UpdateAuthTokenPage,
    SHomePage, SLoginPage,
)

from .fingerprint import FingerprintPage


class AmericanExpressBrowser(TwoFactorBrowser):
    BASEURL = 'https://global.americanexpress.com'
    TWOFA_BASEURL = r'https://functions.americanexpress.com'

    home_login = URL(r'/login\?inav=fr_utility_logout', HomeLoginPage)
    login = URL(r'/myca/logon/emea/action/login', LoginPage)
    fingerprint = URL(r'https://www.cdn-path.com/cc.js\?=&sid=ee490b8fb9a4d570&tid=(?P<transaction_id>.*)&namespace=inauth', FingerprintPage)

    read_auth_challenges = URL(TWOFA_BASEURL + r'/ReadAuthenticationChallenges.v1', ReadAuthChallengePage)
    create_otp_uri = URL(TWOFA_BASEURL + r'/CreateOneTimePasscodeDelivery.v1')
    update_auth_token = URL(TWOFA_BASEURL + r'/UpdateAuthenticationTokenWithChallenge.v1', UpdateAuthTokenPage)
    create_2fa_uri = URL(TWOFA_BASEURL + r'/CreateTwoFactorAuthenticationForUser.v1')

    accounts = URL(r'/api/servicing/v1/member', AccountsPage)
    json_balances = URL(r'/api/servicing/v1/financials/balances', JsonBalances)
    json_balances2 = URL(r'/api/servicing/v1/financials/transaction_summary\?type=split_by_cardmember&statement_end_date=(?P<date>[\d-]+)', JsonBalances2)
    json_pending = URL(
        r'/api/servicing/v1/financials/transactions\?limit=1000&offset=(?P<offset>\d+)&status=pending',
        JsonHistory
    )
    json_posted = URL(
        r'/api/servicing/v1/financials/transactions\?limit=1000&offset=(?P<offset>\d+)&statement_end_date=(?P<end>[0-9-]+)&status=posted',
        JsonHistory
    )
    json_periods = URL(r'/api/servicing/v1/financials/statement_periods', JsonPeriods)
    currency_page = URL(r'https://www.aexp-static.com/cdaas/axp-app/modules/axp-balance-summary/4.7.0/(?P<locale>\w\w-\w\w)/axp-balance-summary.json', CurrencyPage)

    no_card = URL(r'https://www.americanexpress.com/us/content/no-card/',
                  r'https://www.americanexpress.com/us/no-card/', NoCardPage)

    not_found = URL(r'/accounts/error', NotFoundPage)

    SUMMARY_CARD_LABEL = [
        'PAYMENT RECEIVED - THANK YOU',
        'PRELEVEMENT AUTOMATIQUE ENREGISTRE-MERCI',
    ]

    HAS_CREDENTIALS_ONLY = True

    def __init__(self, *args, **kwargs):
        super(AmericanExpressBrowser, self).__init__(*args, **kwargs)

        # State to keep during OTP
        self.authentication_action_id = None
        self.application_id = None
        self.account_token = None
        self.mfa_id = None
        self.auth_trusted = None

        self.__states__ += (
            'authentication_action_id',
            'application_id',
            'account_token',
            'mfa_id',
            'auth_trusted',
        )

        self.AUTHENTICATION_METHODS = {
            'otp': self.handle_otp,
        }

    def init_login(self):
        self.setup_browser_for_login_request()

        transaction_id = self.make_transaction_id()
        now = datetime.datetime.utcnow()

        data = {
            'request_type': 'login',
            'Face': 'fr_FR',
            'Logon': 'Logon',
            'version': 4,
            'inauth_profile_transaction_id': transaction_id,
            'DestPage': urljoin(self.BASEURL,'dashboard'),
            'UserID': self.username,
            'Password': self.password,
            'channel': 'Web',
            'REMEMBERME': 'on',
            'b_hour': now.hour,
            'b_minute': now.minute,
            'b_second': now.second,
            'b_dayNumber': now.day,
            'b_month': now.month,
            'b_year': now.year,
            'b_timeZone': '0',
            'devicePrint': self.make_device_print(),
        }

        self.send_login_request(data)

    def send_login_request(self, data):
        # Match the headers on website to prevent LGON011 error
        headers_for_login = {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
            'Origin': 'https://www.americanexpress.com',
            'Host': 'global.americanexpress.com',

            # Setting headers to None to remove them from the request
            'Referer': None,
            'Upgrade-Insecure-Requests': None,
        }

        self.login.go(data=data, headers=headers_for_login)

        if self.page.get_status_code() != 0:
            error_code = self.page.get_error_code()
            message = self.page.get_error_message()
            if any(code in error_code for code in ('LGON001', 'LGON003')):
                raise BrowserIncorrectPassword(message)
            elif error_code == 'LGON004':
                # This error happens when the website needs the user to
                # enter his card information and reset his password.
                # There is no message returned when this error happens.
                raise ActionNeeded()
            elif error_code == 'LGON008':
                # Don't know what this error means, but if we follow the redirect
                # url it allows us to be correctly logged.
                self.location(self.page.get_redirect_url())
            elif error_code == 'LGON010':
                raise BrowserUnavailable(message)
            elif error_code == 'LGON011':
                # this kind of error is for mystical reasons,
                # but until now it was headers related, it could be :
                # - headers not in the right order
                # - headers with value that doesn't match the one from website
                # - headers missing
                # What's next ?

                if "CBIS_Challenge_Or_Deny" in message:
                    # IP blacklisted
                    raise ScrapingBlocked()
                raise AssertionError('Error code "LGON011" (msg:"%s")' % message)
            elif error_code == 'LGON013':
                self.raise_otp()
            else:
                raise AssertionError('Error code "%s" (msg:"%s") not handled' % (error_code, message))

    def prepare_request(self, req):
        # Get all headers in alphabetical order to prevent LGON011 error
        prep = super(AmericanExpressBrowser, self).prepare_request(req)
        prep.headers = OrderedDict(sorted(prep.headers.items(), key=lambda i: i[0].lower()))
        return prep

    def clear_init_cookies(self):
        # Keep the device-id to prevent an SCA
        for cookie in self.session.cookies:
            if cookie.name == "device-id":
                device = cookie
                break
        else:
            device = None
        self.session.cookies.clear()
        if device:
            self.session.cookies.set_cookie(device)

    def setup_browser_for_login_request(self):
        self.home_login.go()

    def make_transaction_id(self):
        transaction_id = 'LOGIN-%s' % uuid.uuid4()  # Randomly generated in js

        self.register_transaction_id(transaction_id)

        return transaction_id

    def register_transaction_id(self, transaction_id):
        self.fingerprint.go(transaction_id=transaction_id)
        payload = self.page.make_payload_for_s2(transaction_id)
        self.open('https://www.cdn-path.com/s2', method="POST",
            params={
                't': self.page.get_t(),
                'x': 1, # Not seen change yet
                'sid': 'ee490b8fb9a4d570', # Not seen change yet
                'tid': transaction_id,
            },
            files = {
                '_f': payload,
            },
            headers = {
                'Accept-Encoding': 'gzip, deflate, br',
                'Host': 'www.cdn-path.com',
                'Origin': 'https://www.americanexpress.com',
                'Referer': 'https://www.americanexpress.com/',
                'Pragma': 'no-cache',
                'TE': 'Trailers',
            },
        )

    def make_device_print(self):
        d = OrderedDict()
        d['version'] = "3.4.0.0_1"
        d['pm_fpua'] = self.session.headers['User-Agent'] + '|5.0 (X11)|Linux x86_64'
        d['pm_fpsc'] = '24|1650|498|498'
        d['pm_fptw'] = ''
        d['pm_fptz'] = 0
        d['pm_fpln'] = 'lang=en-US|syslang=|userlang='
        d['pm_fpjv'] = 0
        d['pm_fpco'] = 1
        d['pm_fpasw'] = ''
        d['pm_fpan'] = "Netscape"
        d['pm_fpacn'] = "Mozilla"
        d['pm_fpol'] = 'true'
        d['pm_fposp'] = ''
        d['pm_fpup'] = ''
        d['pm_fpsaw'] = '1920'
        d['pm_fpspd'] = '24'
        d['pm_fpsbd'] = ''
        d['pm_fpsdx'] = ''
        d['pm_fpsdy'] = ''
        d['pm_fpslx'] = ''
        d['pm_fpsly'] = ''
        d['pm_fpsfse'] = ''
        d['pm_fpsui'] = ''
        d['pm_os'] = 'Linux'
        d['pm_brmjv'] = 78
        d['pm_br'] = 'Firefox'
        d['pm_inpt'] = ''
        d['pm_expt'] = ''
        return (
            urlencode(d,quote_via=quote) # using quote to prevent encoding space as +
            # The next four character are not quoted by quote
            .replace('~', "%7E")
            .replace('-', "%2D")
            .replace('_', "%5F")
            .replace('.', "%2E")

            # These replace are to remove the & and = included by urlencode
            .replace('=', "%3D")
            .replace('&', "%26")
        )

    def raise_otp(self):
        self.check_interactive()

        reauth = self.page.get_reauth()
        self.authentication_action_id = reauth["actionId"]
        self.application_id = reauth["applicationId"]
        self.mfa_id = reauth["mfaId"]
        self.auth_trusted = reauth["trust"]

        if not self.auth_trusted:
            self.logger.warning(
                "We are not trusted. There could be a problem with the fingerprinting of cc.js"
            )

        read_auth_challenges_payload = [{
            "authenticationActionId": self.authentication_action_id,
            "applicationId": self.application_id,
            "locale": self.locale,
        }]
        self.read_auth_challenges.go(json=read_auth_challenges_payload)

        challenge = self.page.get_challenge()
        assert challenge == "OTP", "We don't know how to handle '%s' challenge." % challenge

        self.account_token = self.page.get_account_token()
        methods = self.page.get_otp_methods()
        delivery_payload, message = self.make_otp_delivery_payload(methods)

        self.create_otp_uri.go(json=delivery_payload)
        raise BrowserQuestion(
            Value('otp', label=message)
        )

    def make_otp_delivery_payload(self, methods):
        known_methods = ["SMS", "EMAIL"]  # This is also our preference order.
        methods = {m["deliveryMethod"]: m for m in methods}

        chosen_method = None

        # Select the 2FA method for this authentification.
        # Search for them in the order of known_methods.
        for known_method in known_methods:
            chosen_method = methods.get(known_method)
            if chosen_method:
                break

        if chosen_method is None:
            assert methods != {}, "Received no challenge option"
            raise AuthMethodNotImplemented(', '.join(methods.keys()))

        delivery_method = chosen_method["deliveryMethod"]
        delivery_payload = [{
            "authenticationActionId": self.authentication_action_id,
            "applicationId": self.application_id,
            "accountToken": self.account_token,
            "locale": self.locale,
            "deliveryMethod": delivery_method,
            "channelType": chosen_method["channelType"],
            "channelEncryptedValue": chosen_method["channelEncryptedValue"],
        }]

        display_value = chosen_method["channelDisplayValue"]
        if delivery_method == "EMAIL":
            message = "Veuillez entrer le code d’authentification qui vous a été envoyé à l'adresse courriel %s." % display_value
        else:
            message = "Veuillez entrer le code d’authentification qui vous a été envoyé au %s." % display_value

        return delivery_payload, message

    def handle_otp(self):
        update_auth_token_payload = [{
            "authenticationActionId": self.authentication_action_id,
            "applicationId": self.application_id,
            "accountToken": self.account_token,
            "locale": self.locale,
            "fieldName": "OTP",
            "fieldValue": self.otp,
        }]
        try:
            self.update_auth_token.go(json=update_auth_token_payload)
            pending_challenge = self.page.get_pending_challenges()
        except ClientError as e:
            self.drop_2fa_state()
            if e.response.status_code == 400 and "UEVE008" in e.response.text:
                # {"description":"Invalid Claim: Data does not match SOR","errorCode":"UEVE008"}
                raise BrowserIncorrectPassword("Mauvais code lors de l'authentification forte.")
            raise

        if pending_challenge != "":
            self.drop_2fa_state()
            raise AssertionError("Multiple challenge not handled by the module yet.")

        self.enrol_device()
        self.tfa_login()
        self.drop_2fa_state()

    def drop_2fa_state(self):
        self.account_token = None
        self.application_id = None
        self.authentication_action_id = None
        self.mfa_id = None
        self.auth_trusted = None

    def enrol_device(self):
        if self.auth_trusted:
            enrol_payload = [{
                "locale": self.locale,
                "trust": self.auth_trusted,
                "deviceName":"Accès Budget Insight pour agrégation",
            }]
            self.create_2fa_uri.go(json=enrol_payload)
        else:
            self.logger.info("Cannot enrol when we are not trusted.")

    def tfa_login(self):
        data = {
            'request_type': "login",
            'Face': 'fr_FR',
            'Logon': 'Logon',
            'version': 4,
            'mfaId': self.mfa_id,
        }
        self.send_login_request(data)

    @property
    def locale(self):
        return self.session.cookies.get_dict(domain=".americanexpress.com")['axplocale']

    @need_login
    def iter_accounts(self):
        self.currency_page.go(locale=self.locale.lower())
        currency = self.page.get_currency()

        self.accounts.go()
        account_list = list(self.page.iter_accounts(currency=currency))
        for account in account_list:
            try:
                # for the main account
                self.json_balances.go(headers={'account_tokens': account.id})
            except HTTPNotFound:
                # for secondary accounts
                self.json_periods.go(headers={'account_token': account._history_token})
                periods = self.page.get_periods()
                period_index = 1
                if len(periods) == 1:  # Recently created accounts have only one period
                    period_index = 0
                self.json_balances2.go(date=periods[period_index], headers={'account_tokens': account.id})
            self.page.fill_balances(obj=account)
            yield account

    @need_login
    def iter_history(self, account):
        self.json_periods.go(headers={'account_token': account._history_token})
        periods = self.page.get_periods()
        today = datetime.date.today()
        # TODO handle pagination
        for p in periods:
            self.json_posted.go(offset=0, end=p, headers={'account_token': account._history_token})
            for tr in self.page.iter_history(periods=periods):
                # As the website is very handy, passing account_token is not enough:
                # it will return every transactions of each account, so we
                # have to match them manually
                if tr._owner == account._idforJSON and tr.date <= today:
                    yield tr

    @need_login
    def iter_coming(self, account):
        # Coming transactions can be found in a 'pending' JSON if it exists
        # ('En attente' tab on the website), as well as in a 'posted' JSON
        # ('Enregistrées' tab on the website)

        # "pending" have no vdate and debit date is in future
        self.json_periods.go(headers={'account_token': account._history_token})
        periods = self.page.get_periods()
        date = parse_date(periods[0]).date()
        today = datetime.date.today()
        # when the latest period ends today we can't know the coming debit date
        if date != today:
            try:
                self.json_pending.go(offset=0, headers={'account_token': account._history_token})
            except ServerError as exc:
                # At certain times of the month a connection might not have pendings;
                # in that case, `json_pending.go` would throw a 502 error Bad Gateway
                error_code = exc.response.json().get('code')
                error_message = exc.response.json().get('message')
                self.logger.warning('No pendings page to access to, got error %s and message "%s" instead.', error_code, error_message)
            else:
                for tr in self.page.iter_history(periods=periods):
                    if tr._owner == account._idforJSON:
                        tr.date = date
                        yield tr

        # "posted" have a vdate but debit date can be future or past
        for p in periods:
            self.json_posted.go(offset=0, end=p, headers={'account_token': account._history_token})
            for tr in self.page.iter_history(periods=periods):
                if tr.date > today or not tr.date:
                    if tr._owner == account._idforJSON:
                        yield tr
                else:
                    return


class AmericanExpressSeleniumFingerprintBrowser(SeleniumBrowser):
    BASEURL = 'https://global.americanexpress.com'

    home_login = URL(r'/login\?inav=fr_utility_logout', SHomePage)
    login = URL(r'https://www.americanexpress.com/en-us/account/login', SLoginPage)

    HEADLESS = True  # Always change to True for prod

    WINDOW_SIZE = (1800, 1000)
    DRIVER = webdriver.Chrome

    def __init__(self, config, *args, **kwargs):
        super(AmericanExpressSeleniumFingerprintBrowser, self).__init__(*args, **kwargs)

    def do_login(self):
        """
        We don't really support login via selenium. We only load the login to execute some
        javascript and then extract cookies + some other values generated in javascript.
        """
        self.home_login.go()
        self.wait_until(IsHereCondition(self.login))


class AmericanExpressWithSeleniumBrowser(SubSeleniumMixin, AmericanExpressBrowser):
    """
    Use a selenium browser to pass the fingerprinting instead of trying to solve it
    manually.

    Selenium is executed at the start of init_login in setup_browser_for_login_request.
    From inside SubSeleniumMixin.do_login, the load_selenium_session method will be called after
    the 'login' process of selenium has finished. That allows to retrieve informations
    that will be needed in the rest of the login process.

    After that, the login proceed as normal except for the overriden make_device_print and
    make make_transaction_id where we used values directly from selenium.
    """

    SELENIUM_BROWSER = AmericanExpressSeleniumFingerprintBrowser

    def __init__(self, *args, **kwargs):
        super(AmericanExpressWithSeleniumBrowser, self).__init__(*args, **kwargs)
        self.selenium_login_transaction_id = None
        self.selenium_device_print = None

        self.selenium_user_agent = None
        self.__states__ += ('selenium_user_agent', )

    def do_login(self, *args, **kwargs):
        AmericanExpressBrowser.do_login(self, *args, **kwargs)

    def load_state(self, *args, **kwargs):
        super(AmericanExpressWithSeleniumBrowser, self).load_state(*args, **kwargs)
        if self.selenium_user_agent:
            self.session.headers['User-Agent'] = self.selenium_user_agent

    def load_selenium_session(self, selenium):
        self.clear_init_cookies()
        super(AmericanExpressWithSeleniumBrowser, self).load_selenium_session(selenium)

        # We need to send this value in the login request.
        self.selenium_login_transaction_id = selenium.driver.execute_script("return window.inauth._cc[0][1].tid;")

        # Save the device print and the user-agent from selenium to replicate the website as much as possible
        self.selenium_device_print = selenium.driver.execute_script('return RSA.encode_deviceprint();')
        self.selenium_user_agent = selenium.driver.execute_script("return navigator.userAgent;")
        self.session.headers['User-Agent'] = self.selenium_user_agent

    def setup_browser_for_login_request(self):
        SubSeleniumMixin.do_login(self)

    def make_device_print(self):
        assert self.selenium_device_print
        return self.selenium_device_print

    def make_transaction_id(self):
        assert self.selenium_login_transaction_id
        return self.selenium_login_transaction_id
