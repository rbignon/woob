# -*- coding: utf-8 -*-

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

from __future__ import unicode_literals

import time
import re
from base64 import b64decode
from datetime import datetime, timedelta
from hashlib import sha256
from uuid import uuid4
from collections import OrderedDict
from decimal import Decimal
from urllib.parse import urljoin, urlparse, parse_qsl, parse_qs, urlencode, urlunparse

from dateutil import parser, tz
from requests.cookies import remove_cookie_by_name
from requests.packages.urllib3.util.ssl_ import create_urllib3_context

from woob.browser import need_login, TwoFactorBrowser
from woob.browser.adapters import HTTPAdapter
from woob.browser.switch import SiteSwitch
from woob.browser.url import URL
from woob.capabilities.bank import (
    Account, AddRecipientStep, Recipient, TransferBankError, Transaction, TransferStep,
    AddRecipientBankError,
)
from woob.capabilities.base import NotAvailable, find_object
from woob.capabilities.bill import Subscription
from woob.capabilities.profile import Profile
from woob.browser.exceptions import BrowserHTTPNotFound, ClientError, LoggedOut, ServerError
from woob.browser.retry import retry_on_logout
from woob.exceptions import (
    BrowserIncorrectPassword, BrowserUnavailable, BrowserHTTPError, BrowserPasswordExpired,
    AuthMethodNotImplemented, AppValidation, AppValidationExpired, BrowserQuestion,
    ActionNeeded,
)
from woob.tools.capabilities.bank.transactions import (
    sorted_transactions, FrenchTransaction, keep_only_card_transactions,
    omit_deferred_transactions,
)
from woob.tools.capabilities.bank.investments import create_french_liquidity
from woob.tools.date import date, now_as_utc
from woob.tools.json import json
from woob.tools.value import Value
from woob.tools.decorators import retry

from .pages import (
    IndexPage, ErrorPage, MarketPage, LifeInsurance, LifeInsuranceHistory, LifeInsuranceInvestments,
    GarbagePage, MessagePage, LoginPage,
    SmsPage, ValidationPageOption, AuthentPage, CanceledAuth,
    CaissedepargneKeyboard, CaissedepargneNewKeyboard,
    TransactionsDetailsPage, LoadingPage, ConsLoanPage, MeasurePage,
    NatixisLIHis, NatixisLIInv, NatixisRedirectPage, NatixisErrorPage,
    SubscriptionPage, CreditCooperatifMarketPage, UnavailablePage,
    CardsPage, CardsComingPage, CardsOldWebsitePage, TransactionPopupPage,
    OldLeviesPage, NewLeviesPage, NewLoginPage, JsFilePage, AuthorizePage,
    AuthenticationMethodPage, VkImagePage, AuthenticationStepPage, LoginTokensPage,
    AppValidationPage, TokenPage, LoginApi, ConfigPage, SAMLRequestFailure,
    ActivationSubscriptionPage, TechnicalIssuePage, UnavailableLoginPage,
    RememberTerminalPage, LogoutPage,
)
from .transfer_pages import (
    CheckingPage, TransferListPage, RecipientPage,
    TransferPage, ProTransferPage, TransferConfirmPage, TransferSummaryPage, ProTransferConfirmPage,
    ProTransferSummaryPage, ProAddRecipientOtpPage, ProAddRecipientPage,
)
from .linebourse_browser import LinebourseAPIBrowser

__all__ = ['CaisseEpargne']


def decode_utf8_cookie(data):
    # caissedepargne/palatine cookies may contain non-ascii bytes which is ill-defined.
    # Actually, they use utf-8.
    # Since it's not standard, requests/urllib interprets it freely... as latin-1
    # and we can't really blame for that.
    # Let's decode this shit ourselves.
    return data.encode('latin-1').decode('utf-8')


def monkeypatch_for_lowercase_percent(session):
    # In the transfer flow, the main site (something like net123.caisse-epargne.fr)
    # redirects to the OTP site (something like www.icgauth.caisse-epargne.fr).
    # %2F is equivalent to %2f, right? It's hexadecimal after all. That's what
    # RFC3986, RFC2396, RFC1630 say, also normalization of case is possible.
    # That's what requests and urllib3 implement.
    # But some dumbasses think otherwise and simply violate the RFCs.
    # They SHOULD [interpreted as described in RFC2119] step away from the computer
    # and never touch it again because they are obviously too stupid to use it.
    # So, we are forced to hack deep in urllib3 to force our custom URL tweaking.

    def patch_attr(obj, attr, func):
        if hasattr(obj, '_old_%s' % attr):
            return

        old_func = getattr(obj, attr)
        setattr(obj, '_old_%s' % attr, old_func)
        setattr(obj, attr, func)

    pm = session.adapters['https://'].poolmanager

    def connection_from_host(*args, **kwargs):
        pool = pm._old_connection_from_host(*args, **kwargs)

        def make_request(conn, method, url, *args, **kwargs):
            if url.startswith('/dacswebssoissuer/AuthnRequestServlet'):
                # restrict this hazardous change to otp urls
                url = re.sub(r'%[0-9A-F]{2}', lambda m: m.group(0).lower(), url)
            return pool._old__make_request(conn, method, url, *args, **kwargs)

        patch_attr(pool, '_make_request', make_request)
        return pool

    patch_attr(pm, 'connection_from_host', connection_from_host)


class LowSecAdapter(HTTPAdapter):
    # caissedepargne uses small DH keys, which is deemed insecure by OpenSSL's default config.
    # we have to lower its expectations so it accepts the certificate.
    # see https://www.ssllabs.com/ssltest/analyze.html?d=www.as-ex-ano-groupe.caisse-epargne.fr for the exhaustive list
    # of defects they are too incompetent to fix

    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context(ciphers="DEFAULT:@SECLEVEL=1")
        kwargs['ssl_context'] = context
        return super(LowSecAdapter, self).init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        context = create_urllib3_context(ciphers="DEFAULT:@SECLEVEL=1")
        kwargs['ssl_context'] = context
        return super(LowSecAdapter, self).proxy_manager_for(*args, **kwargs)


class CaisseEpargneLogin(TwoFactorBrowser):
    HTTP_ADAPTER_CLASS = LowSecAdapter

    # This class is also used by cenet browser
    HAS_CREDENTIALS_ONLY = True
    TWOFA_DURATION = 90 * 24 * 60
    STATE_DURATION = 10
    API_LOGIN = True
    CENET_URL = 'https://www.cenet.caisse-epargne.fr'
    enseigne = 'ce'
    login = URL(
        r'https://www.caisse-epargne.fr/authentification/manage\?step=identification&identifiant=(?P<login>.*)',
        r'https://.*/authentification/manage\?step=identification&identifiant=.*',
        r'https://.*/login.aspx',
        LoginPage
    )

    new_login = URL(r'https://www.caisse-epargne.fr/se-connecter/sso', NewLoginPage)
    js_file = URL(r'https://www.caisse-epargne.fr/se-connecter/main(-|\.).*.js$', JsFilePage)
    config_page = URL(
        r'https://www.caisse-epargne.fr/ria/pas/configuration/config.json\?ts=(?P<timestamp>.*)',
        ConfigPage
    )
    token_page = URL(r'https://www.as-ex-ano-groupe.caisse-epargne.fr/api/oauth/token', TokenPage)
    login_api = URL(
        r'https://www.rs-ex-ano-groupe.caisse-epargne.fr/bapi/user/v1/users/identificationRouting',
        LoginApi
    )
    remember_terminal = URL(
        r'https://www.rs-ex-ath-groupe.caisse-epargne.fr/bapi/user/v1/user/lastConnect',
        RememberTerminalPage
    )
    authorize = URL(r'https://www.as-ex-ath-groupe.caisse-epargne.fr/api/oauth/v2/authorize', AuthorizePage)
    login_tokens = URL(r'https://www.as-ex-ath-groupe.caisse-epargne.fr/api/oauth/v2/consume', LoginTokensPage)

    # Login and transfer authentication
    authentication_step = URL(
        r'https://(?P<domain>www.icgauth.[^/]+)/dacsrest/api/v1u0/transaction/(?P<validation_id>[^/]+)/step',
        AuthenticationStepPage
    )
    authentication_method_page = URL(
        r'https://(?P<domain>www.icgauth.[^/]+)/dacsrest/api/v1u0/transaction/(?P<validation_id>)',
        r'https://www.icgauth.caisse-epargne.fr/dacsrest/api/v1u0/transaction/.*',
        AuthenticationMethodPage,
    )
    saml_failure = URL(r'https://www.icgauth.caisse-epargne.fr/Errors/Errors.html', SAMLRequestFailure)
    vk_image = URL(
        r'https://(?P<domain>www.icgauth.[^/]+)/dacs-rest-media/api/v1u0/medias/mappings/[a-z0-9-]+/images',
        VkImagePage,
    )

    # eg of both possible regexes:
    # https://www.icgauth.caisse-epargne.fr/dacstemplate-SOL/index.html?transactionID=CtxDACSP[a-f0-9]+
    # https://www.icgauth.caisse-epargne.fr/dacstemplate-SOL/_12579/index.html?transactionID=CtxDACSP[a-f0-9]+
    validation_option = URL(
        r'https://(?P<domain>www.icgauth.[^/]+)/dacstemplate-SOL/(?:[^/]+/)?index.html\?transactionID=.*',
        ValidationPageOption
    )
    sms = URL(r'https://(?P<domain>www.icgauth.[^/]+)/dacswebssoissuer/AuthnRequestServlet', SmsPage)
    app_validation = URL(r'https://(?P<domain>www.icgauth.[^/]+)/dacsrest/WaitingCallbackHandler', AppValidationPage)

    account_login = URL(
        r'/authentification/manage\?step=account&identifiant=(?P<login>.*)&account=(?P<accountType>.*)',
        LoginPage
    )
    error = URL(
        r'https://.*/login.aspx',
        r'https://.*/particuliers/Page_erreur_technique.aspx.*',
        ErrorPage
    )
    logout = URL(r'https://.*/Pages/logout.aspx', LogoutPage)

    def __init__(self, nuser, config, *args, **kwargs):
        self.is_cenet_website = False
        self.multi_type = False
        self.accounts = None
        self.typeAccount = None
        self.inexttype = 0  # keep track of index in the connection type's list
        self.nuser = nuser
        self.woob = kwargs['woob']
        self.config = config
        self.browser_switched = False
        self.need_emv_authentication = False
        self.request_information = config['request_information'].get()
        self.auth_type_choice = config.get('auth_type', Value()).get() or ''  # child modules may not use this field
        self.connection_type = None
        self.cdetab = None
        self.continue_url = None
        self.continue_parameters = None
        self.otp_validation = None
        self.login_otp_validation = None  # Used to differentiate from 'transfer/recipient' operations.
        self.term_id = None  # Associated with a validated SCA session (valid for 90 days).
        self.validation_id = None  # Id relating to authentication operations.
        self.validation_domain = None  # Needed to validate authentication operations and can vary among CE's children.

        super(CaisseEpargneLogin, self).__init__(config, *args, **kwargs)

        self.AUTHENTICATION_METHODS = {
            'otp_emv': self.handle_otp_emv,
            'otp_sms': self.handle_otp_sms,
            'resume': self.handle_polling,
        }

        self.RAISE_METHODS = {
            "SMS": self.raise_otp_sms_authentication,
            "CLOUDCARD": self.raise_cloudcard_authentification,
            "EMV": self.raise_otp_emv_authentication,
        }

        self.__states__ += (
            'BASEURL', 'multi_type', 'typeAccount',

            # Transfer/recipient SCA
            'otp_validation',

            # Login SCA
            'login_otp_validation', 'continue_url', 'continue_parameters',
            'term_id',

            # Both SCA
            'validation_id',
            'validation_domain',
        )

    def init_login(self):
        if self.API_LOGIN:
            # caissedepargne pre login changed but children still have the precedent behaviour
            self.do_api_pre_login()
            if self.connection_type == 'ent' and not self.browser_switched:
                raise SiteSwitch('cenet')

            return self.do_new_login()

        authentification_data = self.get_connection_data()
        accounts_types = authentification_data.get('account')

        if not self.browser_switched and self.CENET_URL in authentification_data['url']:
            # the connection type EU could also be used as a criteria
            # We want to avoid to switch again if we are alreay on cenet browser
            raise SiteSwitch('cenet')

        type_account = authentification_data['account'][0]

        if self.multi_type:
            assert type_account == self.typeAccount

        if 'keyboard' in authentification_data:
            self.do_old_login(authentification_data, type_account, accounts_types)
        else:
            # New virtual keyboard
            self.do_new_login(authentification_data)

    def do_api_pre_login(self):
        if not self.cdetab or not self.connection_type:
            data = {
                'grant_type': 'client_credentials',
                'client_id': '8a7e499e-8f67-4377-91d3-74e4cbdd7a42',
                'scope': "",
            }
            self.token_page.go(data=data)
            data = {
                'characteristics': {
                    'iTEntityType': {
                        'code': '02',  # Not found yet, certainly CE code
                        'label': 'CE',
                    },
                    'userCode': self.username,
                    'bankId': None,
                    'subscribeTypeItems': [],
                },
            }
            headers = {
                'Authorization': 'Bearer %s' % self.page.get_access_token(),
            }

            self.login_api.go(json=data, headers=headers)
            self.cdetab = self.page.get_cdetab()
            if self.auth_type_choice:
                if not self.page.is_auth_type_available(self.auth_type_choice):
                    raise BrowserIncorrectPassword(
                        "L'espace client n'a pas été trouvé avec le type de compte renseigné. Veuillez vérifier que le type de compte est correct."
                    )
                self.connection_type = self.auth_type_choice

            if not self.connection_type:
                # no nuser -> part
                # else pro/pp/ent (must be only one available)
                self.connection_type = self.page.get_connection_type()

    def get_cdetab(self):
        if not self.cdetab:
            self.do_api_pre_login()  # this sets cdetab
        return self.cdetab

    def get_connection_data(self):
        """
        Attempt to log in.
        Note: this method does nothing if we are already logged in.
        """
        # Among the parameters used during the login step, there is
        # a connection type (called typeAccount) that can take the
        # following values:
        # WE: espace particulier
        # WP: espace pro
        # WM: personnes protégées
        # EU: Cenet
        #
        # A connection can have one connection type as well as many of
        # them. There is an issue when there is many connection types:
        # the connection type to use can't be guessed in advance, we
        # have to test all of them until the login step is successful
        # (sometimes all connection type can be used for the login, sometimes
        # only one will work).
        #
        # For simplicity's sake, we try each connection type from first to
        # last (they are returned in a list by the first request)
        #
        # Examples of connection types combination that have been seen so far:
        # [WE]
        # [WP]
        # [WE, WP]
        # [WE, WP, WM]
        # [WP, WM]
        # [EU]
        # [EU, WE]  (EU tends to come first when present)

        if not self.username or not self.password:
            raise BrowserIncorrectPassword()

        @retry(ValueError)
        def retry_go_login():
            """
            On occasions the page is not the expected JsonPage,
            although response is a code 200,
            and trying to parse it as such would throw a JSONDecodeError.
            Retrying does the trick and avoids raising a BrowserUnavailable.
            """
            return self.login.go(login=self.username)

        # Retrieve the list of types: can contain a single type or more
        # - when there is a single type: all the information are available
        # - when there are several types: an additional request is needed
        connection = retry_go_login()

        data = connection.get_response()
        if data is None:
            raise BrowserIncorrectPassword()

        data = self.check_connection_data(data)
        assert data is not None
        return data

    def check_connection_data(self, data):
        accounts_types = data.get('account', [])
        if not self.nuser and 'WE' not in accounts_types:
            raise BrowserIncorrectPassword("Utilisez Caisse d'Épargne Professionnels et renseignez votre nuser pour connecter vos comptes sur l'epace Professionels ou Entreprises.")

        if len(accounts_types) > 1:
            # Additional request when there is more than one connection type
            # to "choose" from the list of connection types
            self.multi_type = True

            if self.inexttype < len(accounts_types):
                if accounts_types[self.inexttype] == 'EU' and not self.nuser:
                    # when EU is present and not alone, it tends to come first
                    # if nuser is unset though, user probably doesn't want 'EU'
                    self.inexttype += 1
                elif accounts_types[self.inexttype] == 'WE' and self.nuser:
                    # User is probably a netpro user and want to access their
                    # professional accounts
                    self.inexttype += 1

                self.typeAccount = accounts_types[self.inexttype]
            else:
                raise AssertionError('should have logged in with at least one connection type')
            self.inexttype += 1

            data = self.account_login.go(login=self.username, accountType=self.typeAccount).get_response()

        return data

    def do_old_login(self, authentification_data, type_account, accounts_types):
        # Old virtual keyboard
        id_token_clavier = authentification_data['keyboard']['Id']
        vk = CaissedepargneKeyboard(
            authentification_data['keyboard']['ImageClavier'],
            authentification_data['keyboard']['Num']['string'],
        )

        newCodeConf = vk.get_string_code(self.password)

        payload = {
            'idTokenClavier': id_token_clavier,
            'newCodeConf': newCodeConf,
            'auth_mode': 'ajax',
            'nuusager': self.nuser.encode('utf-8'),
            'codconf': '',  # must be present though empty
            'typeAccount': type_account,
            'step': 'authentification',
            'ctx': 'typsrv={}'.format(type_account),
            'clavierSecurise': '1',
            'nuabbd': self.username,
        }

        try:
            res = self.location(authentification_data['url'], params=payload)
        except ValueError:
            raise BrowserUnavailable()
        if not res.page:
            raise BrowserUnavailable()

        response = res.page.get_response()

        assert response is not None

        if response['error'] == 'Veuillez changer votre mot de passe':
            raise BrowserPasswordExpired(response['error'])

        if not response['action']:
            # the only possible way to log in w/o nuser is on WE. if we're here no need to go further.
            if not self.nuser and self.typeAccount == 'WE':
                raise BrowserIncorrectPassword(self.page.get_wrongpass_message())

            # all typeAccount tested and still not logged
            # next iteration will throw the AssertionError if we don't raise an error here
            if self.inexttype == len(accounts_types):
                raise BrowserIncorrectPassword(self.page.get_wrongpass_message())

            if self.multi_type:
                # try to log in with the next connection type's value
                self.do_login()
                return
            raise BrowserIncorrectPassword(self.page.get_wrongpass_message())

        self.BASEURL = urljoin(authentification_data['url'], '/')

        try:
            self.home.go()
        except BrowserHTTPNotFound:
            raise BrowserIncorrectPassword()

    def fetch_auth_mechanisms_validation_info(self):
        """ First step of strong authentication validation

        This method retrieve all informations needed for validation form.
        Warning: need to be on `validation_option` page to get the "transaction ID".
        """
        transaction_id = re.search(r'transactionID=(.*)', self.page.url)
        if transaction_id:
            transaction_id = transaction_id.group(1)
        else:
            raise AssertionError('Transfer transaction id was not found in url')

        otp_validation_domain = urlparse(self.url).netloc

        self.authentication_method_page.go(
            domain=otp_validation_domain,
            validation_id=transaction_id
        )

        # Can have error at first authentication request.
        # In that case, it's not an invalid otp error.
        # So, return a wrongpass.
        self.page.check_errors(feature='login')

        self.otp_validation = self.page.get_authentication_method_info()

        if self.otp_validation['type'] not in ('SMS', 'CLOUDCARD', 'PASSWORD', 'EMV'):
            self.logger.warning('Not handled authentication method : "%s"' % self.otp_validation['type'])
            raise AuthMethodNotImplemented()

        self.otp_validation['validation_unit_id'] = self.page.validation_unit_id
        self.validation_id = transaction_id
        self.validation_domain = otp_validation_domain

    def handle_2fa_otp(self, otp_type, **params):
        """ Second step of OTP authentication validation

        This method validate OTP SMS or EMV.
        Warning:
        * need to be used through `do_authentication_validation` method
        in order to handle authentication response
        * do not forget to use the first part to have all form information
        """

        # It will occur when states become obsolete
        if not self.otp_validation:
            raise BrowserIncorrectPassword('Le délai pour saisir le code a expiré, veuillez recommencer')

        data = {
            'validate': {
                self.otp_validation['validation_unit_id']: [{
                    'id': self.otp_validation['id'],
                }],
            },
        }

        data_otp = data['validate'][self.otp_validation['validation_unit_id']][0]
        data_otp['type'] = otp_type
        if otp_type == 'SMS':
            # Transfer uses param['opt_sms'] whereas login uses value transient
            data_otp['otp_sms'] = params.get('otp_sms') or self.otp_sms
        elif otp_type == 'EMV':
            # Transfer uses param['opt_sms'] whereas login uses value transient
            data_otp['token'] = params.get('otp_emv') or self.otp_emv

        try:
            self.authentication_step.go(
                domain=self.validation_domain,
                validation_id=self.validation_id,
                json=data
            )
        except (ClientError, ServerError) as e:
            if (
                # "Session Expired" uses HTTP 500, as opposed to other errors which use the HTTP 400 status code.
                # As BPCE may change code status, we don't deal "Session Expired" as a ServerError and other
                # errors as ClientError.
                e.response.status_code in (400, 500)
                and 'error' in e.response.json()
                and e.response.json()['error'].get('code', '') in (104, 105, 106)
            ):
                # Sometimes, an error message is displayed to user :
                # - '{"error":{"code":104,"message":"Unknown validation unit ID"}}'
                # - '{"error":{"code":105,"message":"No session found"}}'
                # - '{"error":{"code":106,"message":"Session Expired"}}'
                # So we give a clear message and clear 'auth_data' to begin from the top next time.
                self.authentification_data = {}
                raise BrowserIncorrectPassword('Votre identification par code a échoué, veuillez recommencer')
            raise

        self.otp_validation = None

    def do_otp_sms_authentication(self, **params):
        self.handle_2fa_otp(otp_type='SMS', **params)

    def raise_otp_sms_authentication(self, **params):
        self._set_login_otp_validation()
        raise BrowserQuestion(self._build_value_otp_sms())

    def raise_cloudcard_authentification(self, **params):
        self._set_login_otp_validation()
        raise AppValidation(message="Veuillez valider votre authentication dans votre application mobile.")

    def do_otp_emv_authentication(self, **params):
        self.handle_2fa_otp(otp_type='EMV', **params)

    def do_cloudcard_authentication(self, **params):
        """ Second step of cloudcard authentication validation

        This method check the application validation status.
        Warning:
        * need to be used through `do_authentication_validation` method
        in order to handle authentication response
        * do not forget to use the first part to have all form information
        """
        assert self.otp_validation

        timeout = time.time() + 300.0
        referer_url = self.authentication_method_page.build(
            domain=self.validation_domain,
            validation_id=self.validation_id,
        )

        while time.time() < timeout:
            self.app_validation.go(
                domain=self.validation_domain,
                headers={'Referer': referer_url},
            )
            status = self.page.get_status()
            # The status is 'valid' even when the user cancels it on
            # the application. The `authentication_step` will return
            # AUTHENTICATION_CANCELED in its response status.
            if status == 'valid':
                self.authentication_step.go(
                    domain=self.validation_domain,
                    validation_id=self.validation_id,
                    json={
                        'validate': {
                            self.otp_validation['validation_unit_id']: [{
                                'id': self.otp_validation['id'],
                                'type': 'CLOUDCARD',
                            }],
                        },
                    },
                )
                break

            assert status == 'progress', 'Unhandled CloudCard status : "%s"' % status
            time.sleep(2)
        else:
            raise AppValidationExpired()

        self.otp_validation = None

    def do_vk_authentication(self, **params):
        """ Authentication with virtual keyboard

        Warning: need to be used through `do_authentication_validation` method
        in order to handle authentication response
        """

        # Can have error at first authentication request.
        # In that case, it's not a vk error, return a wrongpass.
        self.page.check_errors(feature='login')

        validation_unit_id = self.page.validation_unit_id

        vk_info = self.page.get_authentication_method_info()
        vk_id = vk_info['id']
        vk_images_url = vk_info['virtualKeyboard']['externalRestMediaApiUrl']

        self.location(vk_images_url)
        images_url = self.page.get_all_images_data()
        vk = CaissedepargneNewKeyboard(self, images_url)
        code = vk.get_string_code(self.password)

        self.authentication_step.go(
            domain=self.validation_domain,
            validation_id=self.validation_id,
            json={
                'validate': {
                    validation_unit_id: [{
                        'id': vk_id,
                        'password': code,
                        'type': 'PASSWORD',
                    }],
                },
            },
            headers={
                'Referer': self.BASEURL,
                'Accept': 'application/json, text/plain, */*',
            },
        )

        # TODO: remove this when there's no more logs
        if params.get('unknown_security_level'):
            if not self.page.has_validation_unit:
                self.logger.warning('There is no SCA for "%s" security level', params['unknown_security_level'])
            else:
                self.logger.warning(
                    'Security level "%s" has a SCA with authentication method "%s"',
                    params['unknown_security_level'],
                    self.page.get_authentication_method_type()
                )

    def raise_otp_emv_authentication(self, *params):
        if self.page.is_other_authentication_method() and not self.need_emv_authentication:
            # EMV authentication is mandatory every 90 days
            # But by default the authentication mode is EMV
            # let's check if we can use PASSWORD authentication
            doc = self.page.doc
            self.authentication_step.go(
                domain=self.validation_domain,
                validation_id=self.validation_id,
                json={"fallback": {}}
            )

            if self.page.get_authentication_method_type() == 'PASSWORD':
                # To use vk_authentication method we merge the two last json
                # The first one with authentication values and second one with vk values
                doc['step'] = self.page.doc
                self.page.doc = doc
                return self.do_vk_authentication(*params)

            # Need fresh id values to do EMV authentication again
            self.need_emv_authentication = True
            return self.do_login()

        self.check_interactive()

        self._set_login_otp_validation()
        raise BrowserQuestion(self._build_value_otp_emv())

    def _set_login_otp_validation(self):
        self.login_otp_validation = self.page.get_authentication_method_info()
        self.login_otp_validation['validation_unit_id'] = self.page.validation_unit_id

    def _build_value_otp_emv(self):
        return Value(
            "otp_emv",
            label="Veuillez renseigner le code affiché sur le boitier (Lecteur CAP en mode « Code »)"
        )

    def _build_value_otp_sms(self):
        return Value(
            "otp_sms",
            label="Veuillez renseigner le mot de passe unique qui vous a été envoyé par SMS dans le champ réponse."
        )

    def request_fallback(self, original_method):
        # We don't handle this authentification mode yet
        # But we can check if PASSWORD authentification can be done
        current_fallback_request = 0
        max_fallback_request = 5
        current_method = self.page.get_authentication_method_type()
        seen_methods = []
        while (
            current_method != 'PASSWORD'
            and self.page.is_other_authentication_method()
            and current_fallback_request < max_fallback_request
        ):
            seen_methods.append(current_method)
            self.authentication_step.go(
                domain=self.validation_domain,
                validation_id=self.validation_id,
                json={"fallback": {}}
            )
            current_method = self.page.get_authentication_method_type()

        if current_method in ('PASSWORD', 'EMV'):
            # EMV can be not replaceable by PASSWORD (at least once in 90 days).
            # So if we end up with it we have to raise it.
            return current_method
        elif current_method == 'CERTIFICATE':
            raise AuthMethodNotImplemented(
                "Pas de méthode d'authentification disponible pour remplacer la méthode 'CERTIFICAT'."
                + " Cette méthode d'authentification n'est pas gérée."
            )
        else:
            raise AssertionError('Unhandled authentication method: %s' % current_method)

    def handle_otp_emv(self):
        self.otp_validation = self.login_otp_validation
        # `login_otp_validation` is only used to differentiate login related SCA
        # from 'Transfer/Recipient' related SCA.
        # handle_step_validation method uses the `otp_validation` attribute.
        self.login_otp_validation = None
        self.handle_step_validation("EMV", "login")
        self.handle_steps_login()
        self.login_finalize()

    def handle_polling(self):
        self.otp_validation = self.login_otp_validation
        self.login_otp_validation = None
        self.handle_step_validation("CLOUDCARD", "login")
        self.handle_steps_login()
        self.login_finalize()

    def handle_otp_sms(self):
        self.otp_validation = self.login_otp_validation
        self.login_otp_validation = None
        self.handle_step_validation("SMS", "login")
        self.handle_steps_login()
        self.login_finalize()

    def handle_steps_login(self):
        """
        Common code at the end of init_login and handle_* methods for strong
        authentification.

        Will try to solve the steps until an error or the login is successful.
        """
        assert self.authentication_method_page.is_here()
        while self.page.has_validation_unit:
            authentication_method = self.page.get_authentication_method_type()
            if not self.validation_id:
                # The first required authentication operation returns a validation_id
                # which will be required to validate itself and any subsequent authentication
                # operations.
                self.validation_id = self.page.get_validation_id()
                self.validation_domain = urlparse(self.url).netloc

            if not self.validation_id:
                raise AssertionError(
                    "An authentication operation is required but there's no validation id associated with it."
                )
            self.handle_step(authentication_method, "login")
            self.page.check_errors(feature='login')
        self.end_step_process()

    def handle_step(self, authentication_method, feature, **params):
        """
        Send the password or raise a question for the user.
        """
        if authentication_method == "PASSWORD":
            return self.handle_step_validation(authentication_method, feature, **params)

        method_to_use = self.RAISE_METHODS.get(authentication_method)
        if method_to_use is None:
            fallback_method = self.request_fallback(authentication_method)
            return self.handle_step(fallback_method, feature, **params)

        method_to_use(**params)
        # raise_emv can fallback to password and not raise
        # TODO decide if we want to remove this behavior
        # raise AssertionError("An exeption should have been raised by the previous method call.")

    def handle_step_validation(self, authentication_method, feature, **params):
        """
        This method will validate a step. That means sending the password,
        sending a code from the user (sms, emv) ou doing an appval (cloudcard).

        This method will raise an error if it cannot validate a step.
        """
        if authentication_method == 'PASSWORD':
            # If we are not in 'PASSWORD' mode, we know we are in interactive mode already.

            is_sca = self.page.is_sca_expected()
            if is_sca == 'unknown':
                # We can't say whether there will be an SCA or not.
                # In doubt, we need an interactive session and we'll log
                # the security level after the VK login.
                params['unknown_security_level'] = self.page.security_level

            if is_sca or is_sca == 'unknown':
                # TODO Could we search for a password fallback before checking for interactive?
                # TODO Regression: emv could be bypassed sometime in the previous version
                self.check_interactive()

        AUTHENTICATION_METHODS = {
            'SMS': self.do_otp_sms_authentication,
            'CLOUDCARD': self.do_cloudcard_authentication,
            'PASSWORD': self.do_vk_authentication,
            "EMV": self.do_otp_emv_authentication,
        }

        AUTHENTICATION_METHODS[authentication_method](**params)

        assert self.authentication_step.is_here()
        self.page.check_errors(feature=feature)

    def do_authentication_validation(self, authentication_method, feature, **params):
        """ Handle all sort of authentication with `icgauth`

        This method is used transfer/new recipient authentication.

        Parameters:
        authentication_method (str): authentication method in:
        ('SMS', 'CLOUDCARD', 'PASSWORD', 'EMV', 'CERTIFICATE')
        feature (str): action that need authentication in ('transfer', 'recipient')
        """
        self.handle_step_validation(authentication_method, feature, **params)
        self.end_step_process()

    def end_step_process(self):
        self.validation_id = None
        self.validation_domain = None

        redirect_data = self.page.get_redirect_data()
        assert redirect_data, 'redirect_data must not be empty'

        self.location(
            redirect_data['action'],
            data={
                'SAMLResponse': redirect_data['samlResponse'],
            },
            headers={
                'Referer': self.BASEURL,
                'Accept': 'application/json, text/plain, */*',
            },
        )

    def get_bpcesta(self, csid, snid):
        if (
            self.twofa_logged_date
            and now_as_utc() < self.twofa_logged_date + timedelta(minutes=self.TWOFA_DURATION)
        ):
            # TODO: Check logs and remove this if it's not used anymore.
            # Once it's not used we can remove the typ_act logic and only
            # use the term_id.
            if not self.term_id:
                # Single Sign-On allows a user to login without SCA after he performed SCA once.
                typ_act = 'sso'
                self.logger.warning('Add terminal id to an old connection.')
                self.term_id = str(uuid4())
            else:
                typ_act = 'auth'
        else:
            self.term_id = str(uuid4())
            typ_act = 'auth'
        return {
            "csid": csid,
            "typ_app": "rest",
            "enseigne": self.enseigne,
            "typ_sp": "out-band",
            "typ_act": typ_act,  # TODO: hardcode this value to 'auth' once all old connections have a term_id.
            "snid": snid,
            "cdetab": self.cdetab,
            "typ_srv": self.connection_type,
            "term_id": self.term_id,
        }

    def do_new_login(self, authentification_data=''):
        csid = str(uuid4())
        snid = None

        if not self.API_LOGIN:
            self.connection_type = self.page.get_connection_type()
            redirect_url = authentification_data['url']
            parts = list(urlparse(redirect_url))
            url_params = parse_qs(urlparse(redirect_url).query)

            qs = OrderedDict(parse_qsl(parts[4]))
            qs['csid'] = csid
            parts[4] = urlencode(qs)
            url = urlunparse(parts)
            self.cdetab = url_params['cdetab'][0]

            self.continue_url = url_params['continue'][0]
            self.continue_parameters = authentification_data['continueParameters']

            # snid is either present in continue_parameters (creditcooperatif / banquebcp)
            # or in url_params (caissedepargne / other children)
            snid = json.loads(self.continue_parameters).get('snid') or url_params['snid'][0]

            self.location(
                url,
                data='',
                params={
                    'continue_parameters': self.continue_parameters,
                },
            )
        else:
            self.new_login.go(params={'service': 'dei'})

        main_js_file = self.page.get_main_js_file_url()
        self.location(main_js_file)
        if not snid:
            snid = self.page.get_csid()

        client_id = self.page.get_client_id()
        nonce = str(uuid4())  # Not found anymore
        if not self.continue_url:
            timestamp = int(time.time() * 1000)
            self.config_page.go(timestamp=timestamp)
            self.continue_url = self.page.get_continue_url(self.cdetab, self.connection_type)

        # On the website, this sends back json because of the header
        # 'Accept': 'applcation/json'. If we do not add this header, we
        # instead have a form that we can directly send to complete
        # the login.

        claims = {
            'userinfo': {
                'cdetab': None,
                'authMethod': None,
                'authLevel': None,
            },
            'id_token': {
                'auth_time': {"essential": True},
                "last_login": None,
            },
        }

        bpcesta = self.get_bpcesta(csid, snid)

        params = {
            'nonce': nonce,
            'scope': 'openid readUser',
            'response_type': 'id_token token',
            'response_mode': 'form_post',
            'cdetab': self.cdetab,
            'login_hint': self.username,
            'display': 'page',
            'client_id': client_id,
            # don't know if the separators= is really needed
            'claims': json.dumps(claims, separators=(',', ':')),
            'bpcesta': json.dumps(bpcesta, separators=(',', ':')),
        }
        if self.nuser:
            if len(self.username) != 10:
                params['login_hint'] += ' '

            # We must fill with the missing 0 expected by the caissedepargne server
            # Some clues are given in js file
            params['login_hint'] += self.nuser.zfill(6)

        self.authorize.go(params=params)
        try:
            self.page.send_form()
        except ClientError as e:
            if e.response.status_code == 401:
                raise BrowserIncorrectPassword()
            raise

        if (
            self.response.headers.get('Page_Erreur', '') == 'INDISPO'
            or (self.saml_failure.is_here() and self.page.is_unavailable())
        ):
            raise BrowserUnavailable()

        pre_login_status = self.page.get_wrong_pre_login_status()
        if pre_login_status == 'AUTHENTICATION_FAILED':
            saml_response = self.page.get_saml_response()
            if '<saml2p:StatusMessage>NoPlugin</saml2p:StatusMessage>' in b64decode(saml_response).decode('utf8'):
                # The message is hardcoded in the javascript obfuscated
                raise ActionNeeded("L'accès à votre espace bancaire est impossible en raison de données manquantes. Merci de bien vouloir vous rapprocher de votre conseiller.")
            # failing at this step means no password has been submitted yet
            # and no auth method type cannot be recovered
            # corresponding to 'erreur technique' on website
            raise BrowserUnavailable()

        self.validation_id = None  # If the Browser crashes during an authentication operation, we don't want the old validation_id.
        self.handle_steps_login()
        self.login_finalize()

    def login_finalize(self):
        access_token = self.page.get_access_token()
        id_token = self.page.get_id_token()
        data = {
            'id_token': id_token,
            'access_token': access_token,
        }
        if not self.API_LOGIN:
            continue_parameters = json.loads(self.continue_parameters)
            data.update({
                'ctx': continue_parameters['ctx'],
                'redirectUrl': continue_parameters['redirectUrl'],
                'ctx_routage': continue_parameters['ctx_routage'],
            })

        try:
            self.location(self.continue_url, data=data)
        except ClientError as err:
            response = err.response
            if response.status_code == 403 and 'momentanément indisponible' in response.text:
                unavailable_page = UnavailableLoginPage(self, response)
                raise BrowserUnavailable(unavailable_page.get_error_msg())
            raise
        # Url look like this : https://www.net382.caisse-epargne.fr/Portail.aspx
        # We only want the https://www.net382.caisse-epargne.fr part
        parsed_url = urlparse(self.url)
        self.BASEURL = 'https://' + parsed_url.netloc

        headers = {
            'Authorization': 'Bearer %s' % access_token,
            'X-Id-Terminal': self.term_id,
        }
        # As done on the website, this associate the validated SCA with a terminal id.
        # This allows the terminal id to be remembered and bypass the SCA for 90 days.
        self.remember_terminal.go(method='PUT', headers=headers, json={})


class CaisseEpargne(CaisseEpargneLogin):
    BASEURL = "https://www.caisse-epargne.fr"
    HISTORY_MAX_PAGE = 200
    TIMEOUT = 60

    LINEBOURSE_BROWSER = LinebourseAPIBrowser

    loading = URL(r'https://.*/CreditConso/ReroutageCreditConso.aspx', LoadingPage)
    cons_loan = URL(
        r'https://www.credit-conso-cr.caisse-epargne.fr/websavcr-web/rest/contrat/getContrat\?datePourIe=(?P<datepourie>)',
        ConsLoanPage
    )
    transaction_detail = URL(r'https://.*/Portail.aspx.*', TransactionsDetailsPage)
    recipient = URL(r'https://.*/Portail.aspx.*', RecipientPage)
    checking = URL(r'https://.*/Portail.aspx.*', CheckingPage)
    transfer_list = URL(r'https://.*/Portail.aspx.*', TransferListPage)
    transfer = URL(r'https://.*/Portail.aspx.*', TransferPage)
    transfer_summary = URL(r'https://.*/Portail.aspx.*', TransferSummaryPage)
    transfer_confirm = URL(r'https://.*/Portail.aspx.*', TransferConfirmPage)
    pro_transfer = URL(r'https://.*/Portail.aspx.*', ProTransferPage)
    pro_transfer_confirm = URL(r'https://.*/Portail.aspx.*', ProTransferConfirmPage)
    pro_transfer_summary = URL(r'https://.*/Portail.aspx.*', ProTransferSummaryPage)
    pro_add_recipient_otp = URL(r'https://.*/Portail.aspx.*', ProAddRecipientOtpPage)
    pro_add_recipient = URL(r'https://.*/Portail.aspx.*', ProAddRecipientPage)
    measure_page = URL(r'https://.*/Portail.aspx.*', MeasurePage)
    cards_old = URL(r'https://.*/Portail.aspx.*', CardsOldWebsitePage)
    cards = URL(r'https://.*/Portail.aspx.*', CardsPage)
    cards_coming = URL(r'https://.*/Portail.aspx.*', CardsComingPage)
    old_checkings_levies = URL(r'https://.*/Portail.aspx.*', OldLeviesPage)
    new_checkings_levies = URL(r'https://.*/Portail.aspx.*', NewLeviesPage)
    authent = URL(r'https://.*/Portail.aspx.*', AuthentPage)
    subscription = URL(r'https://.*/Portail.aspx\?tache=(?P<tache>).*', SubscriptionPage)
    activation_subscription = URL(r'https://.*/Portail.aspx.*', ActivationSubscriptionPage)
    transaction_popup = URL(r'https://.*/Portail.aspx.*', TransactionPopupPage)
    market = URL(
        r'https://.*/Pages/Bourse.*',
        r'https://www.caisse-epargne.offrebourse.com/ReroutageSJR',
        r'https://www.caisse-epargne.offrebourse.com/fr/6CE.*',
        MarketPage
    )
    unavailable_page = URL(r'https://www.caisse-epargne.fr/.*/au-quotidien', UnavailablePage)

    creditcooperatif_market = URL(r'https://www.offrebourse.com/.*', CreditCooperatifMarketPage)  # just to catch the landing page of the Credit Cooperatif's Linebourse
    life_insurance_history = URL(
        r'https://www.extranet2.caisse-epargne.fr/cin-front/contrats/evenements',
        LifeInsuranceHistory
    )
    life_insurance_investments = URL(
        r'https://www.extranet2.caisse-epargne.fr/cin-front/contrats/details',
        LifeInsuranceInvestments
    )
    life_insurance = URL(
        r'https://.*/Assurance/Pages/Assurance.aspx',
        r'https://www.extranet2.caisse-epargne.fr.*',
        LifeInsurance
    )

    natixis_redirect = URL(
        r'/NaAssuranceRedirect/NaAssuranceRedirect.aspx',
        # TODO: adapt domain to children of CE
        r'https://www.espace-assurances.caisse-epargne.fr/espaceinternet-ce/views/common/routage-itce.xhtml',
        NatixisRedirectPage
    )
    natixis_life_ins_his = URL(
        # TODO: adapt domain to children of CE
        r'https://www.espace-assurances.caisse-epargne.fr/espaceinternet-ce/rest/v2/contratVie/load-operation(?P<account_path>)',
        NatixisLIHis
    )
    natixis_life_ins_inv = URL(
        # TODO: adapt domain to children of CE
        r'https://www.espace-assurances.caisse-epargne.fr/espaceinternet-ce/rest/v2/contratVie/load(?P<account_path>)',
        NatixisLIInv
    )
    natixis_error = URL(
        # TODO: adapt domain to children of CE
        r'https://www.espace-assurances.caisse-epargne.fr/espaceinternet-ce/page500.xhtml',
        NatixisErrorPage
    )

    message = URL(r'https://www.caisse-epargne.offrebourse.com/DetailMessage\?refresh=O', MessagePage)
    home = URL(r'https://.*/Portail.aspx.*', IndexPage)
    home_tache = URL(r'https://.*/Portail.aspx\?tache=(?P<tache>).*', IndexPage)
    garbage = URL(
        r'https://www.caisse-epargne.offrebourse.com/Portefeuille',
        r'https://www.caisse-epargne.fr/particuliers/.*/emprunter.aspx',
        r'https://.*/particuliers/emprunter.*',
        r'https://.*/particuliers/epargner.*',
        r'https://www.caisse-epargne.fr/.*/epargner',
        GarbagePage
    )

    tech_issue = URL(r'https://.*/erreur_technique', TechnicalIssuePage)

    # Accounts managed in life insurance space (not in linebourse)

    insurance_accounts = (
        'AIKIDO',
        'ASSURECUREUIL',
        'ECUREUIL PROJET',
        'GARANTIE RETRAITE EU',
        'INITIATIVES PLUS',
        'INITIATIVES TRANSMIS',
        'LIVRET ASSURANCE VIE',
        'OCEOR EVOLUTION',
        'PATRIMONIO CRESCENTE',
        'PEP TRANSMISSION',
        'PERP',
        'PERSPECTIVES ECUREUI',
        'POINTS RETRAITE ECUR',
        'RICOCHET',
        'SOLUTION PERP',
        'TENDANCES',
        'YOGA',
    )

    def __init__(self, nuser, config, *args, **kwargs):
        self.loans = None
        self.cards_not_reached = False
        self.typeAccount = None
        self.inexttype = 0  # keep track of index in the connection type's list
        self.recipient_form = None
        self.is_send_sms = None
        self.is_use_emv = None
        self.market_url = kwargs.pop(
            'market_url',
            'https://www.caisse-epargne.offrebourse.com',
        )
        self.has_subscription = True

        super(CaisseEpargne, self).__init__(nuser, config, *args, **kwargs)

        self.__states__ += (
            'recipient_form', 'is_send_sms', 'is_app_validation',
            'is_use_emv', 'new_website', 'cards_not_reached',
        )
        dirname = self.responses_dirname
        if dirname:
            dirname += '/bourse'

        self.linebourse = self.LINEBOURSE_BROWSER(
            self.market_url,
            logger=self.logger,
            responses_dirname=dirname,
            woob=self.woob,
            proxy=self.PROXIES,
        )

        monkeypatch_for_lowercase_percent(self.session)

    def load_state(self, state):
        expire = state.get('expire')
        if expire:
            expire = parser.parse(expire)
            if not expire.tzinfo:
                expire = expire.replace(tzinfo=tz.tzlocal())
            if expire < now_as_utc():
                self.logger.info('State expired, not reloading it from storage')
                return

        transfer_states = (
            "recipient_form", "is_app_validation", "is_send_sms", "is_use_emv",
            "otp_validation",
        )

        for transfer_state in transfer_states:
            if transfer_state in state and state[transfer_state] is not None:
                super(CaisseEpargne, self).load_state(state)
                self.logged = True
                break

        # TODO: Always loading the state might break something.
        # if 'login_otp_validation' in state and state['login_otp_validation'] is not None:
        #    super(CaisseEpargne, self).load_state(state)

        super(CaisseEpargne, self).load_state(state)

    def locate_browser(self, state):
        ## in case of transfer/add recipient, we shouldn't go back to previous page
        ## otherwise the site will crash
        transfer_states = (
            "recipient_form", "is_app_validation", "is_send_sms", "is_use_emv",
            "otp_validation",
        )
        for transfer_state in transfer_states:
            if state.get(transfer_state) is not None:
                return

        # after entering the emv otp the locate browser is making a request on
        # the last url we visited, and in that case we are invalidating the
        # validation_unit_id needed for sending the otp
        if self.config['otp_emv'].get() is not None:
            return

        try:
            super(CaisseEpargne, self).locate_browser(state)
        except LoggedOut:
            # If the cookies are expired (it's not clear for how long they last),
            # we'll get redirected to the LogoutPage which will raise a LoggedOut.
            # So we catch it and the login process will start.
            pass

    def deleteCTX(self):
        # For connection to offrebourse and natixis, we need to delete duplicate of CTX cookie
        if len([k for k in self.session.cookies.keys() if k == 'CTX']) > 1:
            del self.session.cookies['CTX']

    def loans_conso(self):
        days = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')
        month = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
        now = datetime.today()
        # for non-DST
        # d = '%s %s %s %s %s:%s:%s GMT+0100 (heure normale d’Europe centrale)' % (days[now.weekday()], now.day, month[now.month - 1], now.year, now.hour, format(now.minute, "02"), now.second)
        # TODO use babel library to simplify this code
        d = '%s %s %s %s %s:%s:%s GMT+0200 (heure d’été d’Europe centrale)' % (
            days[now.weekday()], now.day, month[now.month - 1], now.year,
            now.hour, format(now.minute, "02"), now.second,
        )
        if self.home.is_here():
            msg = self.page.loan_unavailable_msg()
            if msg:
                self.logger.warning('%s' % msg)
                return None
        self.cons_loan.go(datepourie=d)
        return self.page.get_conso()

    def go_measure_list(self, page_num=0):
        self.home.go()

        if not self.measure_page.is_here():
            raise AssertionError('Should be on measure_page')

        self.page.go_measure_list()
        for _ in range(page_num):
            self.page.goto_next_page()

    def get_owner_name(self):
        # Get name from profile to verify who is the owner of accounts.
        name = self.get_profile().name.upper().split(' ', 1)
        if len(name) == 2:  # if the name is complete (with first and last name)
            owner_name = name[1]
        else:  # if there is only first name
            owner_name = name[0]
        return owner_name

    def get_accounts(self, owner_name):
        self.page.check_no_accounts()
        accounts = []
        for page_num in range(20):
            for measure_id in self.page.get_measure_ids():
                self.page.go_measure_accounts_list(measure_id)
                if self.page.check_measure_accounts():
                    for new_account in self.page.get_list(owner_name):
                        # joint accounts can be present twice, once per owner
                        if new_account.id in [account.id for account in accounts]:
                            self.logger.warning('Skip the duplicate account, id :  %s' % new_account.id)
                            continue

                        new_account._info['measure_id'] = measure_id
                        new_account._info['measure_id_page_num'] = page_num
                        accounts.append(new_account)

                self.go_measure_list(page_num)

            if not self.page.has_next_page():
                break
            self.page.goto_next_page()
        return accounts

    @need_login
    def get_measure_accounts_list(self):
        """
        On home page there is a list of "measure" links, each one leading to one person accounts list.
        Iter over each 'measure' and navigate to it to get all accounts
        """
        self.home.go()

        if self.tech_issue.is_here():
            raise BrowserUnavailable()

        owner_name = self.get_owner_name()
        # Make sure we are on list of measures page
        if self.measure_page.is_here():
            self.accounts = self.get_accounts(owner_name)

            for account in self.accounts:
                if 'acc_type' in account._info and account._info['acc_type'] == Account.TYPE_LIFE_INSURANCE:
                    self.go_measure_list(account._info['measure_id_page_num'])
                    self.page.go_measure_accounts_list(account._info['measure_id'])
                    self.page.go_history(account._info)

                    if self.message.is_here():
                        self.page.submit()
                        self.page.go_history(account._info)

                    balance = self.page.get_measure_balance(account)
                    account.balance = Decimal(FrenchTransaction.clean_amount(balance))
                    account.currency = account.get_currency(balance)

        return self.accounts

    def update_linebourse_token(self):
        assert self.linebourse is not None, "linebourse browser should already exist"
        self.linebourse.session.cookies.update(self.session.cookies)
        # It is important to fetch the domain dynamically because
        # for caissedepargne the domain is 'www.caisse-epargne.offrebourse.com'
        # whereas for creditcooperatif it is 'www.offrebourse.com'
        domain = urlparse(self.url).netloc
        self.linebourse.session.headers['X-XSRF-TOKEN'] = self.session.cookies.get('XSRF-TOKEN', domain=domain)

    def add_linebourse_accounts_data(self):
        for account in self.accounts:
            self.deleteCTX()
            if account.type in (Account.TYPE_MARKET, Account.TYPE_PEA):
                self.home_tache.go(tache='CPTSYNT0')
                self.page.go_history(account._info)

                if self.message.is_here():
                    self.page.submit()
                    self.page.go_history(account._info)

                # Some users may not have access to this.
                if not self.market.is_here():
                    continue
                self.page.submit()

                if 'offrebourse.com' in self.url:
                    # Some users may not have access to this.
                    if self.page.is_error():
                        continue

                    self.update_linebourse_token()
                    page = self.linebourse.go_portfolio(account.id)
                    assert self.linebourse.portfolio.is_here()
                    # We must declare "page" because this URL also matches MarketPage
                    account.valuation_diff = page.get_valuation_diff()

                    # We need to go back to the synthesis, else we can not go home later
                    self.home_tache.go(tache='CPTSYNT0')
                else:
                    raise AssertionError("new domain that hasn't been seen so far?")

    def add_card_accounts(self):
        """
        Card cases are really tricky on the new website.
        There are 2 kinds of page where we can find cards information
            - CardsPage: List some of the PSU cards
            - CardsComingPage: On the coming transaction page (for a specific checking account),
                we can find all cards related to this checking account. Information to reach this
                CC is in the home page

        We have to go through this both kind of page for those reasons:
                - If there is no coming yet, the card will not be found in the home page and we will not
                be able to reach the CardsComingPage. But we can find it on CardsPage
                - Some cards are only on the CardsComingPage and not the CardsPage
                - In CardsPage, there are cards (with "Business" in the label) without checking account on the
                website (neither history nor coming), so we skip them.
                - Some card on the CardsPage that have a checking account parent, but if we follow the link to
                reach it with CardsComingPage, we find an other card that is not in CardsPage.
        """
        if self.new_website:
            for account in self.accounts:
                # Adding card's account that we find in CardsComingPage of each Checking account
                if account._card_links:
                    self.home.go()
                    self.page.go_history(account._card_links)
                    for card in self.page.iter_cards():
                        card.parent = account
                        card._coming_info = self.page.get_card_coming_info(card.number, card.parent._card_links.copy())
                        card.ownership = account.ownership
                        card.owner_type = account.owner_type
                        self.accounts.append(card)

        self.home.go()
        self.page.go_list()
        self.page.go_cards()

        # We are on the new website. We already added some card, but we can find more of them on the CardsPage
        if self.cards.is_here():
            for card in self.page.iter_cards():
                card.parent = find_object(self.accounts, number=card._parent_id)
                if not card.parent:
                    self.logger.info(
                        "The parent %s of the card %s wasn't found."
                        % (card._parent_id, card.id)
                    )
                    continue

                card.owner_type = card.parent.owner_type

                # If we already added this card, we don't have to add it a second time
                if find_object(self.accounts, number=card.number):
                    continue

                info = card.parent._card_links

                # If card.parent._card_links is not filled, it mean this checking account
                # has no coming transactions.
                card._coming_info = None
                card.ownership = card.parent.ownership
                if info:
                    self.page.go_list()
                    self.page.go_history(info)
                    card._coming_info = self.page.get_card_coming_info(card.number, info.copy())

                    if not card._coming_info:
                        self.logger.warning('Skip card %s (not found on checking account)', card.number)
                        continue
                self.accounts.append(card)

        # We are on the old website. We add all card that we can find on the CardsPage
        elif self.cards_old.is_here():
            for card in self.page.iter_cards():
                card.parent = find_object(self.accounts, number=card._parent_id)
                assert card.parent, 'card account parent %s was not found' % card.number
                card.owner_type = card.parent.owner_type
                self.accounts.append(card)

    def add_owner_accounts(self):
        owner_name = self.get_owner_name()

        if self.home.is_here():
            self.page.check_no_accounts()
            self.page.go_list()
        else:
            self.home.go()

        self.accounts = list(self.page.get_list(owner_name))

        try:
            # Get wealth accounts that are not on the summary page
            self.home_tache.go(tache='EPASYNT0')
            # If there are no wealth accounts we are redirected to the "garbage page"
            if self.home.is_here():
                for account in self.page.get_list(owner_name):
                    if account.id not in [acc.id for acc in self.accounts]:
                        if account.type == Account.TYPE_LIFE_INSURANCE and "MILLEVIE" not in account.label:
                            # For life insurance accounts, we check if the contract is still open,
                            # Except for MILLEVIE insurances, because the flow is different
                            # and we can't check at that point.
                            if not self.go_life_insurance_investments(account):
                                continue
                            if self.page.is_contract_closed():
                                continue
                        self.accounts.append(account)
            wealth_not_accessible = False

        except ServerError:
            self.logger.warning("Could not access wealth accounts page (ServerError)")
            wealth_not_accessible = True
        except ClientError as e:
            resp = e.response
            if resp.status_code == 403 and "Ce contenu n'existe pas." in resp.text:
                self.logger.warning("Could not access wealth accounts page (ClientError)")
                wealth_not_accessible = True
            else:
                raise

        if wealth_not_accessible:
            # The navigation can be broken here
            # We first check if we are logout
            # and if it is the case we do login again
            try:
                # if home.go reached LogoutPage,
                # LoggedOut exception avoids to finish add_owner_accounts()
                # and add_card_accounts() must be done after the next do_login
                self.cards_not_reached = True
                self.home.go()
            except BrowserUnavailable:
                if not self.error.is_here():
                    raise
                self.do_login()
                self.cards_not_reached = False

        self.add_linebourse_accounts_data()
        self.add_card_accounts()

    def check_accounts_exist(self):
        """
        Sometimes for connections that have no accounts we get stuck in the `ActivationSubscriptionPage`.
        The `check_no_accounts` inside the `get_measure_accounts_list` is never reached.
        """
        self.home.go()
        if not self.activation_subscription.is_here():
            return
        self.page.send_check_no_accounts_form()
        assert self.activation_subscription.is_here(), 'Expected to be on ActivationSubscriptionPage'
        self.page.check_no_accounts()

    @retry_on_logout()
    @need_login
    @retry(ClientError, tries=3)
    def get_accounts_list(self):
        self.check_accounts_exist()

        if self.accounts is None:
            self.accounts = self.get_measure_accounts_list()

        if self.accounts is None:
            self.add_owner_accounts()

        if self.cards_not_reached:
            # The navigation has been broken during wealth navigation
            # We must finish accounts return with add_card_accounts()
            self.add_card_accounts()
            self.cards_not_reached = False

        # Some accounts have no available balance or label and cause issues
        # in the backend so we must exclude them from the accounts list:
        self.accounts = [account for account in self.accounts if account.label and account.balance != NotAvailable]
        for account in self.accounts:
            yield account

    @retry_on_logout()
    @need_login
    def get_loans_list(self):
        if self.loans is None:
            self.loans = []

            if self.home.is_here():
                if self.page.check_no_accounts() or self.page.check_no_loans():
                    return []

            for _ in range(2):
                self.home_tache.go(tache='CRESYNT0')
                if self.tech_issue.is_here():
                    raise BrowserUnavailable()

                if self.home.is_here():
                    if not self.page.is_access_error():
                        # The server often returns a 520 error (Undefined):
                        try:
                            self.loans = list(self.page.get_loan_list())
                        except ServerError:
                            self.logger.warning('Access to loans failed, we try again')
                        else:
                            # We managed to reach the Loans JSON
                            break

            for _ in range(3):
                try:
                    self.home_tache.go(tache='CPTSYNT0')

                    if self.home.is_here():
                        self.page.go_list()
                except ClientError:
                    pass
                else:
                    break

        return iter(self.loans)

    # For all account, we fill up the history with transaction. For checking account, there will have
    # also deferred_card transaction too.
    # From this logic, if we send "account_card", that mean we recover all transactions from the parent
    # checking account of the account_card, then we filter later the deferred transaction.
    @need_login
    def _get_history(self, info, account_card=None):
        # Only fetch deferred debit card transactions if `account_card` is not None
        if isinstance(info['link'], list):
            info['link'] = info['link'][0]
        if not info['link'].startswith('HISTORIQUE'):
            return
        if 'measure_id' in info:
            self.home_tache.go(tache='CPTSYNT0')
            self.go_measure_list(info['measure_id_page_num'])
            self.page.go_measure_accounts_list(info['measure_id'])
        elif self.home.is_here():
            self.page.go_list()
        else:
            self.home_tache.go(tache='CPTSYNT0')

        self.page.go_history(info)

        # ensure we are on the correct history page
        if 'netpro' in self.page.url and not self.page.is_history_of(info['id']):
            self.page.go_history_netpro(info)

        # In this case, we want the coming transaction for the new website
        # (old website return coming directly in `get_coming()` )
        if account_card and info and info['type'] == 'HISTORIQUE_CB':
            self.page.go_coming(account_card._coming_info['link'])

        info['link'] = [info['link']]

        for i in range(self.HISTORY_MAX_PAGE):

            assert self.home.is_here()

            # list of transactions on account page
            transactions_list = []
            card_and_forms = []
            for tr in self.page.get_history():
                transactions_list.append(tr)
                if tr.type == tr.TYPE_CARD_SUMMARY:
                    if account_card:
                        if self.card_matches(tr.card, account_card.number):
                            card_and_forms.append((tr.card, self.page.get_form_to_detail(tr)))
                        else:
                            self.logger.debug(
                                'will skip summary detail (%r) for different card %r',
                                tr, account_card.number
                            )
                elif tr.type == FrenchTransaction.TYPE_CARD and 'fac cb' in tr.raw.lower() and not account_card:
                    # for immediate debits made with a def card the label is way too empty for certain clients
                    # we therefore open a popup and find the rest of the label
                    # can't do that for every type of transactions because it makes a lot a additional requests
                    form = self.page.get_form_to_detail(tr)
                    transaction_popup_page = self.open(form.url, data=form)
                    tr.raw += ' ' + transaction_popup_page.page.complete_label()

            # For deferred card history only :
            #
            # Now that we find transactions that have TYPE_CARD_SUMMARY on the checking account AND the account_card number we want,
            # we browse deferred card transactions that are resume by that list of TYPE_CARD_SUMMARY transaction.

            # Checking account transaction:
            #  - 01/01 - Summary 5134XXXXXX103 - 900.00€ - TYPE_CARD_SUMMARY  <-- We have to go in the form of this tr to get
            #   cards details transactions.
            for card, form in card_and_forms:
                form.submit()
                if self.home.is_here() and self.page.is_access_error():
                    self.logger.warning('Access to card details is unavailable for this user')
                    continue
                assert self.transaction_detail.is_here()
                for tr in self.page.get_detail():
                    tr.type = Transaction.TYPE_DEFERRED_CARD
                    if account_card:
                        tr.card = card
                        tr.bdate = tr.rdate
                    transactions_list.append(tr)
                if self.new_website:
                    self.page.go_newsite_back_to_summary()
                else:
                    self.page.go_form_to_summary()

                # going back to summary goes back to first page
                for _ in range(i):
                    assert self.page.go_next()

            #  order by date the transactions without the summaries
            transactions_list = sorted_transactions(transactions_list)

            for tr in transactions_list:
                yield tr

            assert self.home.is_here()

            if not self.page.go_next():
                return

        raise AssertionError('More than {} history pages'.format(self.HISTORY_MAX_PAGE))

    @need_login
    def _get_history_invests(self, account):
        if self.home.is_here():
            self.page.go_list()
        else:
            self.home.go()

        if account._info['type'] == 'SYNTHESE_EPARGNE':
            # If the type is not SYNTHESE_EPARGNE, it means we have a direct link and going
            # this way would set off a SyntaxError.
            self.page.go_history(account._info)

        if account.type in (Account.TYPE_LIFE_INSURANCE, Account.TYPE_CAPITALISATION, Account.TYPE_PERP):
            if self.page.is_account_inactive(account.id):
                self.logger.warning('Account %s %s is inactive.' % (account.label, account.id))
                return []

            if "MILLEVIE" in account.label:
                # This way we ensure we can access all type of MILLEVIE accounts
                self.home_tache.go(tache='EPASYNT0')
                self.page.go_life_insurance(account)

                self.natixis_life_ins_inv.go(account_path=account._natixis_url_path)
                if self.natixis_error.is_here():
                    raise BrowserUnavailable()

                if not self.page.has_history():
                    return []

                try:
                    self.natixis_life_ins_his.go(account_path=account._natixis_url_path)
                except BrowserHTTPError as e:
                    if e.response.status_code == 500:
                        error = json.loads(e.response.text)
                        raise BrowserUnavailable(error["error"])
                    raise
                return sorted_transactions(self.page.get_history())

            if account.label.startswith('NUANCES ') or account.label in self.insurance_accounts:
                # Some life insurances are not on the accounts summary
                self.home_tache.go(tache='EPASYNT0')
                self.page.go_life_insurance(account)
                # To access the life insurance space, we need to delete the JSESSIONID cookie
                # to avoid an expired session
                # There might be duplicated JSESSIONID cookies (eg with different paths),
                # that's why we need to use remove_cookie_by_name()
                remove_cookie_by_name(self.session.cookies, 'JSESSIONID')

            if self.home.is_here():
                # no detail available for this account
                return []

            try:
                if not self.life_insurance.is_here() and not self.message.is_here():
                    # life insurance website is not always available
                    raise BrowserUnavailable()
                self.page.submit()
                self.life_insurance_history.go()
                # Life insurance transactions are not sorted by date in the JSON
                return sorted_transactions(self.page.iter_history())
            except ServerError as e:
                if e.response.status_code == 500:
                    raise BrowserUnavailable()
                raise

        return self.page.iter_history()

    @retry_on_logout()
    @need_login
    def get_history(self, account):
        self.home.go()
        self.deleteCTX()

        if account.type == account.TYPE_CARD:
            def match_cb(tr):
                return self.card_matches(tr.card, account.number)

            hist = self._get_history(account.parent._info, account)
            hist = keep_only_card_transactions(hist, match_cb)
            return hist

        if not hasattr(account, '_info'):
            raise NotImplementedError
        if (
            account.type in (Account.TYPE_LIFE_INSURANCE, Account.TYPE_CAPITALISATION)
            and 'measure_id' not in account._info
        ):
            return self._get_history_invests(account)
        if account.type in (Account.TYPE_MARKET, Account.TYPE_PEA):
            self.page.go_history(account._info)
            if "Bourse" in self.url:
                self.page.submit()
                if 'offrebourse.com' in self.url:
                    # Some users may not have access to this.
                    if self.page.is_error():
                        return []

                    self.linebourse.session.cookies.update(self.session.cookies)
                    self.update_linebourse_token()
                    history = self.linebourse.iter_history(account.id)
                    # We need to go back to the synthesis, else we can not go home later
                    self.home_tache.go(tache='CPTSYNT0')
                    return history

        hist = self._get_history(account._info, False)
        return omit_deferred_transactions(hist)

    @retry_on_logout()
    @need_login
    def get_coming(self, account):
        if account.type == account.TYPE_CHECKING:
            return self.get_coming_checking(account)
        elif account.type == account.TYPE_CARD:
            return self.get_coming_card(account)
        return []

    def get_coming_checking(self, account):
        # The accounts list or account history page does not contain comings for checking accounts
        # We need to go to a specific levies page where we can find past and coming levies (such as recurring ones)
        trs = []
        self.home.go()
        if 'measure_id' in getattr(account, '_info', ''):
            self.go_measure_list(account._info['measure_id_page_num'])
            self.page.go_measure_accounts_list(account._info['measure_id'])
            self.page.go_history(account._info)

        self.page.go_cards()  # need to go to cards page to have access to the nav bar where we can choose LeviesPage from
        if not self.page.levies_page_enabled():
            return trs
        self.page.go_levies()  # need to go to a general page where we find levies for all accounts before requesting a specific account
        if not self.page.comings_enabled(account.id):
            return trs
        self.page.go_levies(account.id)
        if self.new_checkings_levies.is_here() or self.old_checkings_levies.is_here():
            today = datetime.today().date()
            # Today transactions are in this page but also in history page, we need to ignore it as a coming
            for tr in self.page.iter_coming():
                if tr.date > today:
                    trs.append(tr)
        return trs

    def get_coming_card(self, account):
        trs = []
        if not hasattr(account.parent, '_info'):
            raise NotImplementedError()
        # We are on the old website
        if hasattr(account, '_coming_eventargument'):
            if not self.cards_old.is_here():
                self.home.go()
                self.page.go_list()
                self.page.go_cards()
            self.page.go_card_coming(account._coming_eventargument)
            return sorted_transactions(self.page.iter_coming())
        # We are on the new website.
        info = account.parent._card_links
        # if info is empty, that means there are no comings yet
        if info:
            for tr in self._get_history(info.copy(), account):
                tr.type = tr.TYPE_DEFERRED_CARD
                trs.append(tr)
        return sorted_transactions(trs)

    @retry_on_logout()
    @need_login
    def get_investment(self, account):
        self.deleteCTX()

        investable_types = (
            Account.TYPE_LIFE_INSURANCE, Account.TYPE_CAPITALISATION,
            Account.TYPE_MARKET, Account.TYPE_PEA,
        )
        if (
            account.type not in investable_types
            or 'measure_id' in account._info
        ):
            raise NotImplementedError()

        if account.type == Account.TYPE_PEA and account.label == 'PEA NUMERAIRE':
            yield create_french_liquidity(account.balance)
            return

        if self.home.is_here():
            self.page.go_list()
        else:
            self.home.go()

        if account.type in (Account.TYPE_MARKET, Account.TYPE_PEA):
            self.page.go_history(account._info)
            # Some users may not have access to this.
            if not self.market.is_here():
                return
            self.page.submit()

            if 'offrebourse.com' in self.url:
                # Some users may not have access to this.
                if self.page.is_error():
                    return

                self.update_linebourse_token()
                for investment in self.linebourse.iter_investments(account.id):
                    yield investment

                # We need to go back to the synthesis, else we can not go home later
                self.home_tache.go(tache='CPTSYNT0')
                return

        elif account.type in (Account.TYPE_LIFE_INSURANCE, Account.TYPE_CAPITALISATION):
            if account._info['type'] == 'SYNTHESE_EPARGNE':
                # If the type is not SYNTHESE_EPARGNE, it means we have a direct link and going
                # this way would set off a SyntaxError.
                self.page.go_history(account._info)

            if self.page.is_account_inactive(account.id):
                self.logger.warning('Account %s %s is inactive.' % (account.label, account.id))
                return
            if "MILLEVIE" in account.label:
                # This way we ensure we can access all type of MILLEVIE accounts
                self.home_tache.go(tache='EPASYNT0')
                self.page.go_life_insurance(account)
                self.natixis_life_ins_inv.go(account_path=account._natixis_url_path)
                if self.natixis_error.is_here():
                    raise BrowserUnavailable()
                for tr in self.page.get_investments():
                    yield tr
                return

            if not self.go_life_insurance_investments(account):
                return

        if self.garbage.is_here():
            self.page.come_back()
            return
        for i in self.page.iter_investment():
            yield i
        if self.market.is_here():
            self.page.come_back()

    @need_login
    def go_life_insurance_investments(self, account):
        # Returns whether it managed to go to the page
        self.home_tache.go(tache='EPASYNT0')
        self.page.go_life_insurance(account)
        if self.home.is_here():
            # no detail is available for this account
            return False
        elif not self.market.is_here() and not self.message.is_here():
            # life insurance website is not always available
            raise BrowserUnavailable()
        self.page.submit()
        try:
            self.life_insurance_investments.go()
        except ServerError:
            raise BrowserUnavailable()
        return True

    @retry_on_logout()
    @need_login
    def iter_market_orders(self, account):
        if account.type not in (Account.TYPE_MARKET, Account.TYPE_PEA):
            return
        self.home.go()
        self.deleteCTX()
        self.page.go_history(account._info)
        if "Bourse" in self.url:
            self.page.submit()
            if 'offrebourse.com' in self.url:
                # Some users may not have access to this.
                if self.page.is_error():
                    return
                self.linebourse.session.cookies.update(self.session.cookies)
                self.update_linebourse_token()
                try:
                    for order in self.linebourse.iter_market_orders(account.id):
                        yield order
                finally:
                    # We need to go back to the synthesis, else we can not go home later
                    self.home_tache.go(tache='CPTSYNT0')

    @need_login
    def get_advisor(self):
        raise NotImplementedError()

    @retry_on_logout()
    @need_login
    def get_profile(self):
        profile = Profile()
        if len([k for k in self.session.cookies.keys() if k == 'CTX']) > 1:
            del self.session.cookies['CTX']

        ctx = decode_utf8_cookie(self.session.cookies.get('CTX', str()))
        # str() to make sure a native str is used as expected by decode_utf8_cookie
        headerdei = decode_utf8_cookie(self.session.cookies.get('headerdei', str()))
        if 'username=' in ctx:
            profile.name = re.search('username=([^&]+)', ctx).group(1)
        elif 'nomusager=' in headerdei:
            profile.name = re.search('nomusager=(?:[^&]+/ )?([^&]+)', headerdei).group(1)
        return profile

    @retry_on_logout()
    @need_login
    def iter_recipients(self, origin_account):
        if origin_account.type in [Account.TYPE_LOAN, Account.TYPE_CARD, Account.TYPE_MARKET]:
            return []

        if 'measure_id' in getattr(origin_account, '_info', ''):
            self.home.go()
            self.home_tache.go(tache='MESLIST0')

        if 'pro' in self.url:
            # If transfer is not yet allowed, the next step will send a sms to the customer to validate it
            self.page.go_pro_transfer_availability()
            if not self.page.is_transfer_allowed():
                return []

        # Transfer unavailable
        try:
            self.pre_transfer(origin_account)
        except TransferBankError:
            return []

        go_transfer_errors = (
            # redirected to home page because:
            # - need to relogin, see `self.page.need_auth()`
            # - need more security, see `self.page.transfer_unavailable()`
            # - transfer is not available for this connection, see `self.page.go_transfer_via_history()`
            # TransferPage inherit from IndexPage so self.home.is_here() is true, check page type to avoid this problem
            type(self.page) is IndexPage,
            # check if origin_account have recipients
            self.transfer.is_here() and not self.page.can_transfer(origin_account),
        )
        if any(go_transfer_errors):
            recipients = []
        else:
            recipients = self.page.iter_recipients(account_id=origin_account.id)

        if 'measure_id' in getattr(origin_account, '_info', ''):
            # need return to measure home to avoid broken navigation
            self.home.go()
            self.home_tache.go(tache='MESLIST0')
        return recipients

    def pre_transfer(self, account):
        if self.home.is_here():
            if 'measure_id' in getattr(account, '_info', ''):
                self.go_measure_list(account._info['measure_id_page_num'])
                self.page.go_measure_accounts_list(account._info['measure_id'])
            else:
                self.page.go_list()
        else:
            self.home.go()
        self.page.go_transfer(account)

    @need_login
    def init_transfer(self, account, recipient, transfer):
        self.is_send_sms = False
        self.is_use_emv = False
        self.is_app_validation = False
        self.pre_transfer(account)

        if self.pro_transfer.is_here():
            # OTP validation does not work for pro users, and all transfers
            # requires an otp validation.
            raise NotImplementedError()

        # Warning: this may send a sms or an app validation
        self.page.init_transfer(account, recipient, transfer)

        if self.validation_option.is_here():
            self.fetch_auth_mechanisms_validation_info()

            if self.otp_validation['type'] == 'SMS':
                self.is_send_sms = True
                raise TransferStep(transfer, self._build_value_otp_sms())
            elif self.otp_validation['type'] == 'EMV':
                self.is_use_emv = True
                raise TransferStep(transfer, self._build_value_otp_emv())
            elif self.otp_validation['type'] == 'CLOUDCARD':
                self.is_app_validation = True
                raise AppValidation(
                    resource=transfer,
                    message="Veuillez valider le transfert sur votre application mobile.",
                )

        if 'netpro' in self.url:
            return self.page.create_transfer(account, recipient, transfer)

        self.page.continue_transfer(account.label, recipient.label, transfer.label)
        return self.page.update_transfer(transfer, account, recipient)

    @need_login
    def otp_validation_continue_transfer(self, transfer, **params):
        assert (
            'resume' in params
            or 'otp_sms' in params
            or 'otp_emv' in params
        ), 'otp_sms or otp_emv or resume is missing'

        if 'resume' in params:
            self.is_app_validation = False

            self.do_authentication_validation(
                authentication_method='CLOUDCARD',
                feature='transfer',
            )
        elif 'otp_sms' in params:
            self.is_send_sms = False

            self.do_authentication_validation(
                authentication_method='SMS',
                feature='transfer',
                otp_sms=params['otp_sms']
            )
        elif 'otp_emv' in params:
            self.is_use_emv = False

            self.do_authentication_validation(
                authentication_method='EMV',
                feature='transfer',
                otp_emv=params['otp_emv']
            )

        if self.transfer.is_here():
            self.page.continue_transfer(transfer.account_label, transfer.recipient_label, transfer.label)
            return self.page.update_transfer(transfer)
        raise AssertionError('Blank page instead of the TransferPage')

    @need_login
    def execute_transfer(self, transfer):
        self.page.confirm()
        return self.page.populate_reference(transfer)

    def get_recipient_obj(self, recipient):
        r = Recipient()
        r.iban = recipient.iban
        r.id = recipient.iban
        r.label = recipient.label
        r.category = u'Externe'
        r.enabled_at = datetime.now().replace(microsecond=0)
        r.currency = u'EUR'
        r.bank_name = NotAvailable
        return r

    def post_sms_password(self, otp, otp_field_xpath):
        data = {}
        for k, v in self.recipient_form.items():
            if k != 'url':
                data[k] = v
        data[otp_field_xpath] = otp
        self.location(self.recipient_form['url'], data=data)
        self.recipient_form = None

    def facto_post_recip(self, recipient):
        self.page.post_recipient(recipient)
        self.page.confirm_recipient()
        return self.get_recipient_obj(recipient)

    def end_sms_recipient(self, recipient, **params):
        self.post_sms_password(params['sms_password'], 'uiAuthCallback__1_')
        self.page.post_form()
        self.page.go_on()
        self.facto_post_recip(recipient)

    def end_pro_recipient(self, recipient, **params):
        self.post_sms_password(params['pro_password'], 'MM$ANR_WS_AUTHENT$ANR_WS_AUTHENT_SAISIE$txtReponse')
        return self.facto_post_recip(recipient)

    @retry(CanceledAuth)
    @need_login
    def new_recipient(self, recipient, **params):
        if 'sms_password' in params:
            return self.end_sms_recipient(recipient, **params)

        if 'otp_sms' in params or 'resume' in params:
            if 'otp_sms' in params:
                self.do_authentication_validation(
                    authentication_method='SMS',
                    otp_sms=params['otp_sms'],
                    feature='recipient'
                )
            else:
                self.do_authentication_validation(
                    authentication_method='CLOUDCARD',
                    feature='recipient'
                )

            if self.authent.is_here():
                self.page.go_on()
                return self.facto_post_recip(recipient)

        if 'pro_password' in params:
            return self.end_pro_recipient(recipient, **params)

        first_transfer_account = next(
            acc
            for acc in self.get_accounts_list()
            if acc.type in (Account.TYPE_CHECKING, Account.TYPE_SAVINGS)
        )
        self.pre_transfer(first_transfer_account)
        # This send sms to user.
        self.page.go_add_recipient()

        if self.transfer.is_here():
            self.page.handle_error()
            raise AssertionError('We should not be on this page')

        if self.validation_option.is_here():
            self.fetch_auth_mechanisms_validation_info()

            recipient_obj = self.get_recipient_obj(recipient)
            if self.otp_validation['type'] == 'SMS':
                self.is_send_sms = True
                raise AddRecipientStep(recipient_obj, self._build_value_otp_sms())
            elif self.otp_validation['type'] == 'CLOUDCARD':
                self.is_app_validation = True
                raise AppValidation(
                    resource=recipient_obj,
                    message="Veuillez valider l'ajout de bénéficiaire sur votre application mobile."
                )

        # pro add recipient.
        elif self.page.need_auth():
            self.page.set_browser_form()
            raise AddRecipientStep(
                self.get_recipient_obj(recipient),
                Value('pro_password', label=self.page.get_prompt_text())
            )

        elif self.home.is_here():
            # If we land here it might be because the user has no 2fa method
            # enabled, and therefore cannot add a recipient.
            unavailable_2fa = self.page.get_unavailable_2fa_message()
            if unavailable_2fa:
                raise AddRecipientBankError(message=unavailable_2fa)
            raise AssertionError('Should not be on home page after sending sms when adding new recipient.')

        else:
            self.page.check_canceled_auth()
            self.page.set_browser_form()
            raise AddRecipientStep(
                self.get_recipient_obj(recipient),
                Value('sms_password', label=self.page.get_prompt_text())
            )

    def go_documents_without_sub(self):
        self.home_tache.go(tache='CPTSYNT0')
        assert self.subscription.is_here(), "Couldn't go to documents page"

    @retry_on_logout()
    @need_login
    def iter_subscription(self):
        self.home.go()
        # CapDocument is not implemented for professional accounts yet
        if any(x in self.url for x in ["netpp", "netpro"]):
            raise NotImplementedError()
        self.home_tache.go(tache='CPTSYNT1')
        if self.unavailable_page.is_here():
            # some users don't have checking account
            self.home_tache.go(tache='EPASYNT0')
        if self.garbage.is_here():  # User has no subscription, checking if they have documents, if so creating fake subscription
            self.has_subscription = False
            self.home_tache.go(tache='CPTSYNT0')
            if not self.subscription.is_here():  # Looks like there is nothing to return
                return []
            self.logger.warning("Couldn't find subscription, creating a fake one to return documents available")

            profile = self.get_profile()

            sub = Subscription()
            sub.label = sub.subscriber = profile.name
            sub.id = sha256(profile.name.lower().encode('utf-8')).hexdigest()

            return [sub]

        # if we are not on checkings page, we don't have documents
        if not self.checking.is_here():
            return []

        self.page.go_subscription()

        if self.activation_subscription.is_here():
            raise ActionNeeded("Si vous souhaitez accéder à vos documents dématérialisés, vous devez activer le service e-Document dans votre espace personnel Caisse d'Épargne")

        if not self.subscription.is_here():
            # If we're not on the subscription page we should be on the IndexPage
            assert self.home.is_here()

            email_needed = self.page.get_email_needed_message()

            # if user is not allowed to have subscription we return an empty list
            if self.page.is_subscription_unauthorized():
                return []
            # If user hasn't given a personal e-mail address, the website asks
            # for the user to set one.
            elif email_needed:
                raise ActionNeeded(email_needed)
            else:
                raise AssertionError("Unhandled redirection to IndexPage")

        if self.page.has_subscriptions():
            return self.page.iter_subscription()
        return []

    @retry_on_logout()
    @need_login
    def iter_documents(self, subscription):
        self.home.go()
        if not self.has_subscription:
            self.go_documents_without_sub()
            for doc in self.page.iter_documents(sub_id=subscription.id, has_subscription=self.has_subscription):
                yield doc
        else:
            today = date.today()

            self.home_tache.go(tache='CPTSYNT1')
            if self.unavailable_page.is_here():
                # some users don't have checking account
                self.home_tache.go(tache='EPASYNT0')
            self.page.go_subscription()
            # setting to have 3 years of history
            for year in range(today.year - 2, today.year + 1):
                self.page.change_year(year)

                assert self.subscription.is_here()

                for doc in self.page.iter_documents(sub_id=subscription.id, has_subscription=self.has_subscription):
                    yield doc

    @retry_on_logout()
    @need_login
    def download_document(self, document):
        self.home.go()
        if not self.has_subscription:
            self.go_documents_without_sub()
            return self.page.download_document(document).content
        self.home_tache.go(tache='CPTSYNT1')
        if self.unavailable_page.is_here():
            # some users don't have checking account
            self.home_tache.go(tache='EPASYNT0')
        self.page.go_subscription()
        assert self.subscription.is_here()
        self.page.change_year(document.date.year)
        assert self.subscription.is_here()

        return self.page.download_document(document).content

    def card_matches(self, a, b):
        # For the same card, depending where we scrape it, we have
        # more or less visible number. `X` are visible number, `*` hidden one's.
        # tr.card: XXXX******XXXXXX, account.number: XXXXXX******XXXX
        return (a[:4], a[-4:]) == (b[:4], b[-4:])

    @retry_on_logout()
    @need_login
    def iter_transfers(self, account):
        self.home.go()
        self.page.go_checkings()
        self.page.go_transfer_list()

        for transfer in self.page.iter_transfers():
            self.page.open_transfer(transfer._formarg)
            self.page.fill_transfer(obj=transfer)
            yield transfer

    @retry_on_logout()
    @need_login
    def iter_emitters(self):
        self.home.go()
        if self.page.go_emitters() is False:
            return []
        return self.page.iter_emitters()
