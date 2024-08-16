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


import time
from base64 import b64decode
from datetime import date, timedelta
from urllib.parse import urlparse
from uuid import uuid4

from dateutil import parser, tz
from jose import jwt

from woob.browser.adapters import LowSecHTTPAdapter
from woob.browser.browsers import need_login
from woob.browser.exceptions import ClientError, LoggedOut, ServerError
from woob.browser.mfa import TwoFactorBrowser
from woob.browser.switch import SiteSwitch
from woob.browser.url import URL
from woob.capabilities.bank import (
    Account, AccountOwnerType,
)
from woob.exceptions import (
    ActionNeeded, ActionType, AppValidation, AppValidationExpired,
    AuthMethodNotImplemented, BrowserIncorrectPassword, BrowserQuestion,
    BrowserUnavailable, OTPSentType, SentOTPQuestion,
)
from woob.tools.capabilities.bank.transactions import sorted_transactions
from woob.tools.date import now_as_utc
from woob.tools.json import json
from woob.tools.value import Value
from woob_modules.linebourse.browser import LinebourseAPIBrowser

from .document_pages import DocumentsPage, SubscriptionPage
from .pages import (
    AccountsPage, AppValidationPage, AuthenticationMethodPage,
    AuthenticationStepPage, AuthorizePage, CaissedepargneNewKeyboard,
    CardsPage, ComingTransactionsPage, ConfigPage, ConsumerCreditDetailsPage,
    CreditCooperatifMarketPage, ExtranetReroutingPage, HomePage, JsFilePage,
    LeaveLineBoursePage, LifeInsuranceHistory, LifeInsuranceInvestments,
    LinebourseReroutingPage, LoanDetailsPage, LoginApi, LoginPage, LoginTokensPage,
    MarketPage, PrepareReroutingPage, RememberTerminalPage, RevolvingDetailsPage,
    RevolvingHistoryPage, SAMLRequestFailure, SmsPage, TokenPage, TransactionsPage,
    ValidationPageOption, VkImagePage,
)

__all__ = ['CaisseEpargne']


class CaisseEpargneLogin(TwoFactorBrowser):
    HTTP_ADAPTER_CLASS = LowSecHTTPAdapter
    BASEURL = 'https://www.caisse-epargne.fr'
    AS_ATH_GROUP_BASEURL = 'https://www.as-ext-bad-ce.caisse-epargne.fr'
    RS_ATH_GROUP_BASEURL = 'https://www.rs-ext-bad-ce.caisse-epargne.fr'

    # This class is also used by cenet browser
    HAS_CREDENTIALS_ONLY = True
    TWOFA_DURATION = 90 * 24 * 60
    STATE_DURATION = 10
    CENET_URL = 'https://www.cenet.caisse-epargne.fr'
    enseigne = 'ce'

    # In order to prevent child modules using their own BASEURL,
    # do not remove BASEURL from URLs here except if this URL is
    # redefined in the child.
    login = URL(r'https://www.caisse-epargne.fr/se-connecter/sso', LoginPage)
    # Each js_file URL contains a different client_id that can be needed
    js_file = URL(
        r'https://www.caisse-epargne.fr/se-connecter/main\..*\.js',
        r'https://www.caisse-epargne.fr/espace-client/main\..*\.js',
        r'https://www.caisse-epargne.fr/gestion-client/credit-immobilier/main\..*\.js',
        r'https://www.caisse-epargne.fr/espace-gestion/pret-personnel/main\..*\.js',
        JsFilePage
    )
    config_page = URL(
        r'https://www.caisse-epargne.fr/ria/pas/configuration/config.json\?ts=(?P<timestamp>.*)',
        ConfigPage
    )
    token_page = URL(r'https://www.as-ex-ano-groupe.caisse-epargne.fr/api/oauth/v2/token', TokenPage)
    login_api = URL(
        r'https://www.rs-ex-ano-groupe.caisse-epargne.fr/bapi/user/v1/users/identificationRouting',
        LoginApi
    )
    # This home_page is full of JS and, as is, is not really a useful homepage. But still,
    # the website uses it as a homepage and we need some information on it to be able to
    # browse the API.
    home_page = URL(r'https://www.caisse-epargne.fr/espace-client/compte', HomePage)
    remember_terminal = URL(
        r'/bapi/user/v1/user/lastConnect',
        RememberTerminalPage,
        base='RS_ATH_GROUP_BASEURL',
    )
    authorize = URL(
        r'/api/oauth/v2/authorize',
        AuthorizePage,
        base='AS_ATH_GROUP_BASEURL',
    )
    login_tokens = URL(
        r'/api/oauth/v2/consume',
        LoginTokensPage,
        base='AS_ATH_GROUP_BASEURL',
    )
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

    def __init__(self, nuser, config, *args, **kwargs):
        self.nuser = nuser
        self.config = config
        self.browser_switched = False
        self.need_emv_authentication = False
        self.request_information = config['request_information'].get()
        self.auth_type_choice = config.get('auth_type', Value()).get() or ''  # child modules may not use this field
        self.connection_type = None
        self.cdetab = None
        self.csid = None
        self.snid = None
        self.nonce = None
        self.second_client_id = None
        self.x_bpce_sessionid = None
        self.continue_url = None
        self.ent_or_pro_username = None
        self.authorization_token = None
        self.otp_validation = None
        self.login_otp_validation = None  # Used to differentiate from 'transfer/recipient' operations.
        self.term_id = None  # Associated with a validated SCA session (valid for 90 days).
        self.validation_id = None  # Id relating to authentication operations.
        self.validation_domain = None  # Needed to validate authentication operations and can vary among CE's children.
        self.id_token = None

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
            'BASEURL',

            # All these attributes must be kept for the last authorization process
            'csid', 'snid', 'nonce', 'x_bpce_sessionid',
            'cdetab', 'connection_type', 'ent_or_pro_username',

            # Login SCA
            'login_otp_validation', 'continue_url',
            'term_id', 'otp_validation',

            # Both SCA
            'validation_id',
            'validation_domain',

            # Browsing API after login
            'authorization_token',
        )

    def init_login(self):
        self.do_api_pre_login()
        if self.connection_type == 'pp' and not self.browser_switched:
            raise SiteSwitch('old')
        elif self.connection_type == 'ent' and not self.browser_switched:
            raise SiteSwitch('cenet')

        return self.do_api_login()

    def do_api_pre_login(self):
        # Even though we post the username at some point in this method,
        # the real login process is not done here. At that point, we only
        # post the username to get a lot of required data for the do_api_login()
        # method that will be called after and in which we'll use the credentials
        # in order to really login.

        if not self.term_id:
            self.term_id = str(uuid4())
        self.csid = str(uuid4())
        self.nonce = str(uuid4())

        self.login.go(params={'service': 'dei'})

        main_js_file = self.page.get_main_js_file_url()
        self.location(main_js_file)

        if not self.snid:
            self.snid = self.page.get_snid(self.enseigne.upper())

        self.first_client_id = self.page.get_first_client_id()
        self.second_client_id = self.page.get_second_client_id()

        if not self.cdetab or not self.connection_type:
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.first_client_id,
                'scope': '',
            }
            self.token_page.go(data=data)

            bank_id = ''
            if self.enseigne != 'ce':
                # bankId parent value is empty but it must
                # be provided as the cdetab for child modules
                bank_id = self.cdetab

            data = {
                'characteristics': {
                    'iTEntityType': {
                        'code': '02',
                        'label': self.enseigne.upper(),
                    },
                    'userCode': self.username,
                    'bankId': bank_id,
                    'subscribeTypeItems': [],
                },
            }
            self.login_api.go(
                json=data,
                headers={'Authorization': 'Bearer %s' % self.page.get_access_token()},
            )

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

        if not self.continue_url:
            # continue_url, as named by the website, is a redirect_uri needed
            # during the multiple authorization processes.
            timestamp = int(time.time() * 1000)
            self.config_page.go(timestamp=timestamp)
            self.continue_url = self.page.get_continue_url(self.cdetab, self.connection_type)

    def get_cdetab(self):
        # Useful for child modules
        if not self.cdetab:
            self.do_api_pre_login()  # this sets cdetab
        return self.cdetab

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
        raise SentOTPQuestion(
            field_name="otp_sms",
            message="Veuillez renseigner le mot de passe unique qui vous a été envoyé par SMS dans le champ réponse.",
            medium_type=OTPSentType.SMS,
        )

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
                # We have to check if an SCA is excpected and if so, we have to check
                # if we are in interactive mode, because the bank can send an SMS when
                # we validate the VK.
                if self.page.is_sca_expected():
                    self.check_interactive()
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
        return {
            'csid': csid,
            'typ_app': 'rest',
            'enseigne': self.enseigne,
            'typ_sp': 'out-band',
            'typ_act': 'auth',
            'snid': snid,
            'cdetab': self.cdetab,
            'typ_srv': self.connection_type,
            'phase': '',
            'term_id': self.term_id,
        }

    def do_api_login(self):
        # On the website, this sends back json because of the header
        # 'Accept': 'applcation/json'. If we do not add this header, we
        # instead have a form that we can directly send to complete
        # the login.

        bpcesta = self.get_bpcesta(self.csid, self.snid)

        params = {
            'nonce': self.nonce,
            'response_type': 'id_token token',
            'response_mode': 'form_post',
            'cdetab': self.cdetab,
            'login_hint': self.username,
            'redirect_uri': self.continue_url,
            'display': 'page',
            'client_id': self.second_client_id,
            'claims': json.dumps(
                {
                    'userinfo': {
                        'cdetab': None,
                        'authMethod': None,
                        'authLevel': None,
                        'dacsId': None,
                        'last_login': None,
                        'auth_time': None,
                        'opsId': None,
                        'appid': None,
                        'pro': None,
                        'userRef': None,
                        'apidp': None,
                        'bpAttributeId': None,
                        'env': None,
                    },
                    'id_token': {
                        'auth_time': {'essential': True},
                        'last_login': None,
                        'cdetab': None,
                        'pro': None,
                    },
                },
                separators=(',', ':'),
            ),
            'bpcesta': json.dumps(bpcesta, separators=(',', ':')),
        }

        if self.nuser:
            self.ent_or_pro_username = self.username
            if len(self.username) != 10:
                self.ent_or_pro_username += ' '

            # We must fill with the missing 0 expected by the caissedepargne server
            # Some clues are given in js file
            self.ent_or_pro_username += self.nuser.zfill(6)
            params['login_hint'] = self.ent_or_pro_username

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
                raise ActionNeeded(
                    locale="fr-FR", message="L'accès à votre espace bancaire est impossible en raison de données manquantes. Merci de bien vouloir vous rapprocher de votre conseiller.",
                    action_type=ActionType.CONTACT,
                )
            # failing at this step means no password has been submitted yet
            # and no auth method type cannot be recovered
            # corresponding to 'erreur technique' on website
            raise BrowserUnavailable()

        self.validation_id = None  # If the Browser crashes during an authentication operation, we don't want the old validation_id.
        self.handle_steps_login()
        self.login_finalize()

    def handle_last_authorize(self):
        # This needs to be in a specific method because it can also be
        # called when having to iter history or investments for a
        # non-cash PEA or a market account.
        params = {
            'scope': '',
            'cdetab': self.cdetab,
            'client_id': self.third_client_id,
            'response_type': 'id_token token',
            'nonce': self.nonce,
            'response_mode': 'form_post',
            'claims': json.dumps(
                {
                    'id_token': {'cdetab': None, 'pro': None},
                    'userinfo': {'pro': None, 'cdetab': None, 'authMethod': None, 'authLevel': None},
                },
                separators=(',', ':'),
            ),
            'bpcesta': json.dumps(
                {
                    'typ_sp': 'out-band',
                    'cdetab': self.cdetab,
                    'enseigne': self.enseigne,
                    'login_hint': self.login_hint,
                    'typ_srv': self.connection_type,
                    'typ_app': 'rest',
                    'typ_act': 'sso',
                }, separators=(',', ':'),
            ),
            'login_hint': self.login_hint,
            'display': 'page',
        }
        self.authorize.go(params=params)

        self.page.get_form().submit()

        self.login_tokens.go(
            data={'SAMLResponse': self.page.get_saml_response()},
            headers={'Accept': 'application/json, text/plain, */*'},
        )
        self.authorization_token = self.page.get_access_token()
        self.session.headers['Authorization'] = f'Bearer {self.authorization_token}'

    def login_finalize(self):
        access_token = self.page.get_access_token()
        self.id_token = self.page.get_id_token()

        headers = {
            'Authorization': 'Bearer %s' % access_token,
            'X-Id-Terminal': self.term_id,
        }
        # As done on the website, this associate the validated SCA with a terminal id.
        # This allows the terminal id to be remembered and bypass the SCA for 90 days.

        # TODO: reverse some JS to understand the browser fingerprinting. While this
        # terminal ID is still used, they added something that has still to be
        # determined to enforce the 2FA. For the moment, SCA won't be remembered in any way.
        self.remember_terminal.go(method='PUT', headers=headers, json={})

        data = {
            'id_token': self.id_token,
            'access_token': access_token,
        }

        if self.connection_type == 'pp':
            self.location(self.continue_url, data=data)
            # # Here we should be logged on old pp ("personnes protégées") space
            return

        elif self.connection_type == 'ent':
            # Fetch data for cenet last authorization
            self.location(self.continue_url, data=data)
            self.js_file.go(js_file_name=self.page.get_main_js_file_url())
            self.third_client_id = self.page.get_third_client_id_for_cenet()

        else:
            # Fetch data for regular last authorization
            params = {
                'cdetab': self.cdetab,
                'typ_srv': self.connection_type,
                'login_hint': self.username,
                'typ_app': 'rest',
                'typ_sp': 'out-band',
                'enseigne': self.enseigne,
                'snid': self.snid,
                'csid': self.csid,
            }
            self.home_page.go(params=params)

            main_js_file = self.page.get_main_js_file_url()
            self.location(main_js_file)
            self.third_client_id = self.page.get_third_client_id()

        self.login_hint = self.username
        if self.nuser:
            self.login_hint = self.ent_or_pro_username

        self.handle_last_authorize()


class CaisseEpargne(CaisseEpargneLogin):
    BASEURL = 'https://www.caisse-epargne.fr'
    EXTRANET_BASEURL = 'https://www.extranet2.caisse-epargne.fr'
    TIMEOUT = 30

    LINEBOURSE_BROWSER = LinebourseAPIBrowser

    accounts_page = URL(
        r'/bapi/contract/v2/augmentedSynthesisViews',
        AccountsPage,
        base='RS_ATH_GROUP_BASEURL',
    )
    cards_page = URL(
        r'/bapi/card/v2/cardCarouselViews/search/byUser',
        CardsPage,
        base='RS_ATH_GROUP_BASEURL',
    )
    accounts_coming = URL(
        r'/pfm/user/v1.1/upcoming',
        ComingTransactionsPage,
        base='RS_ATH_GROUP_BASEURL',
    )
    history_page = URL(
        r'/pfm/user/v1\.1/transactions',
        TransactionsPage,
        base='RS_ATH_GROUP_BASEURL',
    )
    # Mandatory to access either linebourse or extranet spaces
    prepare_rerouting = URL(
        r'/bapi/contract/v1/contracts/(?P<website_id>.*)/prepareRouting',
        PrepareReroutingPage,
        base='RS_ATH_GROUP_BASEURL',
    )
    linebourse_rerouting = URL(
        r'https://www.caisse-epargne.offrebourse.com/ReroutageSJR',
        LinebourseReroutingPage
    )
    extranet_rerouting = URL(
        r'/cin-front/Authentification',
        ExtranetReroutingPage,
        base='EXTRANET_BASEURL',
    )
    leave_linebourse = URL(
        r'https://www.espace-bourse.caisse-epargne.fr/rest/access/logout',
        LeaveLineBoursePage
    )
    revolving_details = URL(
        r'/bapi/revolvingCredit/v1/revolvingCreditSynthesisViews/(?P<revolving_id>.*)',
        RevolvingDetailsPage,
        base='RS_ATH_GROUP_BASEURL',
    )
    revolving_history = URL(
        r'/bapi/revolvingCredit/v1/revolvingCredits/(?P<revolving_id>.*)/financialTransactions',
        RevolvingHistoryPage,
        base='RS_ATH_GROUP_BASEURL',
    )
    consumer_credit_home = URL(r'https://www.caisse-epargne.fr/espace-gestion/pret-personnel/#/', HomePage)
    consumer_credit_details = URL(
        r'/bapi/personalLoanPrd/v1/personalLoanPrdSynthesisView/(?P<consumer_credit_id>.*)',
        ConsumerCreditDetailsPage,
        base='RS_ATH_GROUP_BASEURL',
    )
    loan_home = URL(r'https://www.caisse-epargne.fr/gestion-client/credit-immobilier/', HomePage)
    loan_details = URL(
        r'/bapi/loan/v1/loans/(?P<loan_id>.*)',
        LoanDetailsPage,
        base='RS_ATH_GROUP_BASEURL',
    )
    life_insurance_history = URL(
        r'/cin-front/contrats/evenements',
        LifeInsuranceHistory,
        base='EXTRANET_BASEURL',
    )
    life_insurance_investments = URL(
        r'/cin-front/contrats/details',
        LifeInsuranceInvestments,
        base='EXTRANET_BASEURL',
    )
    market = URL(
        r'https://.*/Pages/Bourse.*',
        r'https://www.caisse-epargne.offrebourse.com/ReroutageSJR',
        r'https://www.caisse-epargne.offrebourse.com/fr/6CE.*',
        r'https://www.caisse-epargne.offrebourse.com/app-v2/#/app-mobile',
        MarketPage
    )
    creditcooperatif_market = URL(r'https://www.offrebourse.com/.*', CreditCooperatifMarketPage)  # just to catch the landing page of the Credit Cooperatif's Linebourse

    subscription = URL(r'https://www.rs-ex-ath-groupe.caisse-epargne.fr/bapi/user/v2/user', SubscriptionPage)
    documents = URL(r'https://www.net444.caisse-epargne.fr/Portail.aspx', DocumentsPage)

    def __init__(self, nuser, config, *args, **kwargs):
        self.default_transactions_number = 250
        self.history_maximum_days = 365
        self.market_url = kwargs.pop(
            'market_url',
            'https://www.caisse-epargne.offrebourse.com',
        )

        super(CaisseEpargne, self).__init__(nuser, config, *args, **kwargs)

        dirname = self.responses_dirname
        if dirname:
            dirname += '/bourse'

        self.linebourse = self.LINEBOURSE_BROWSER(
            self.market_url,
            logger=self.logger,
            responses_dirname=dirname,
            proxy=self.PROXIES,
        )

    def load_state(self, state):
        expire = state.get('expire')
        if expire:
            expire = parser.parse(expire)
            if not expire.tzinfo:
                expire = expire.replace(tzinfo=tz.tzlocal())
            if expire < now_as_utc():
                self.logger.info('State expired, not reloading it from storage')
                return

        # TODO: Always loading the state might break something.
        # if 'login_otp_validation' in state and state['login_otp_validation'] is not None:
        #    super(CaisseEpargne, self).load_state(state)

        super(CaisseEpargne, self).load_state(state)

    def locate_browser(self, state):
        # after entering the emv otp the locate browser is making a request on
        # the last url we visited, and in that case we are invalidating the
        # validation_unit_id needed for sending the otp
        if any((self.config['otp_emv'].get(), self.config['otp_sms'].get())):
            return

        if self.authorization_token:
            # If the token isn't valid anymore (it's usable for approximately 10 minutes),
            # 403 response will trigger a new login, as needed.
            self.session.headers['Authorization'] = f'Bearer {self.authorization_token}'

        try:
            super(CaisseEpargne, self).locate_browser(state)
        except LoggedOut:
            # If the cookies are expired (it's not clear for how long they last),
            # we'll get redirected to the LogoutPage which will raise a LoggedOut.
            # So we catch it and the login process will start.
            pass

    def leave_linebourse_space(self):
        # Mandatory to avoid having to do a new login
        # on caissedepargne after leaving linebourse
        self.leave_linebourse.go()
        self.handle_last_authorize()

    def update_linebourse_token(self):
        assert self.linebourse is not None, "linebourse browser should already exist"
        self.linebourse.session.cookies.update(self.session.cookies)
        # It is important to fetch the domain dynamically because
        # for caissedepargne the domain is 'www.caisse-epargne.offrebourse.com'
        # whereas for creditcooperatif it is 'www.offrebourse.com'
        domain = urlparse(self.url).netloc
        self.linebourse.session.headers['X-XSRF-TOKEN'] = self.session.cookies.get('XSRF-TOKEN', domain=domain)

    def get_loans_token(self, account_type):
        # This authorization process is close to the one we do at the end of the login
        # and is needed to access some of the 'bapi' URLs for loans and consumer credits.
        # Authorization token must only be used for the right URLs, setting it for the session
        # would mess with the authorization token that we already have to navigate through
        # regular accounts.
        if account_type == 'loans':
            self.loan_home.go()
            self.location(self.page.get_main_js_file_url())
            self.loans_client_id = self.page.get_loans_client_id()
        elif account_type == 'consumer_credits':
            # We could fetch the consumer credits client_id dynamically ; it has
            # its own consumer_credit_home URL that leads us to the JS containing
            # the client id but that JS page is really huge and woob can take up to
            # two minutes for it's regexp to match the pattern. If the client_id ever
            # changes (pretty unlikely, some client IDs have been hardcoded for a very long time),
            # finding a faster way to dynamically fetch that data might be necessary.
            self.loans_client_id = '30c229b8-047f-49a0-aad4-198008c1cdd7'

        params = {
            'scope': '',
            'cdetab': self.cdetab,
            'client_id': self.loans_client_id,
            'response_type': 'token',
            'nonce': self.nonce,
            'response_mode': 'form_post',
            'bpcesta': json.dumps(
                {
                    'cdetab': self.cdetab,
                    'typ_srv': self.connection_type,
                    'typ_sp': 'out-band',
                    'enseigne': self.enseigne,
                    'typ_app': 'rest',
                    'typ_act': 'sso',
                },
                separators=(',', ':')
            ),
            'display': 'page',
        }
        try:
            self.authorize.go(params=params)
        except ClientError as e:
            if e.response.status_code == 400:
                raise AssertionError('Consumer credits client_id might have changed, check if it must be updated.')
            raise

        self.page.get_form().submit()

        self.login_tokens.go(
            data={'SAMLResponse': self.page.get_saml_response()},
            headers={'Accept': 'application/json, text/plain, */*'},
        )

        return 'Bearer %s' % self.page.get_access_token()

    @need_login
    def iter_accounts(self):
        params = {
            'productFamilyPFM': '1,2,3,4,6,7,17',
            'pfmCharacteristicsIndicator': 'true',
        }
        self.accounts_page.go(params=params)

        accounts = []
        cards = []

        for account in self.page.iter_accounts():
            accounts.append(account)
            if account._has_card:
                cards.extend(self.page.iter_cards(parent_account=account))

        for loan in self.page.iter_loans():
            if loan.type == Account.TYPE_REVOLVING_CREDIT:
                self.revolving_details.go(revolving_id=loan.id)
                self.page.fill_revolving_details(obj=loan)
            elif loan.type == Account.TYPE_CONSUMER_CREDIT:
                try:
                    self.consumer_credit_details.go(
                        consumer_credit_id=loan.id,
                        headers={'Authorization': self.get_loans_token('consumer_credits')}
                    )
                except ClientError as e:
                    if e.response.status_code == 400:
                        # Some "Prets conso" seem to have a specific way
                        # to access their details, if they have any details.
                        pass
                    else:
                        raise
                else:
                    self.page.fill_consumer_credit_details(obj=loan)
            elif loan.type == Account.TYPE_LOAN:
                self.loan_details.go(
                    loan_id=loan._website_id,
                    headers={'Authorization': self.get_loans_token('loans')},
                )
                self.page.fill_loan_details(obj=loan)
            accounts.append(loan)

        if cards:
            # Get some card details
            self.cards_page.go(params={'userId': 'currentUser'})
            for card in cards:
                self.page.fill_cards(card)
                # We currently cannot retrieve the old card id for the second owner
                # of cards on a joint account. We need to set an id or it will crash.
                # TODO Audit how to reach every card owner CardsPage.
                if not card.id:
                    card.id = card._details_id
            accounts.extend(cards)

        return accounts

    def go_to_secondary_space(self, space, account):
        # Account details are located on linebourse or extranet space.
        data = {
            'characteristics': {
                'contractActionType': {
                    'code': '',
                    'label': '',
                },
                'productFamilyPFM': {
                    'code': '',
                    'label': '',
                },
                'returnUrl': {},
            },
            'response': {
                'code': '',
                'interactionId': '',
                'label': '',
            },
        }
        self.prepare_rerouting.go(json=data, website_id=account._website_id)

        if space == 'linebourse':
            self.linebourse_rerouting.go(data=self.page.get_linebourse_redirection_data())
            self.linebourse.session.cookies.update(self.session.cookies)
            self.update_linebourse_token()
        elif space == 'extranet':
            self.extranet_rerouting.go(data=self.page.get_extranet_redirection_data())

    def handle_pagination(self, params, iter_method):
        # Only way to know if there are more transactions
        # is to get the total number of transactions from
        # a first call to the history route and then call
        # that same history route with updated parameters
        # each time until we reach the total number of
        # transactions.
        transactions_list = list(iter_method(self.page))
        total_transactions_number = self.page.get_total_transactions_number()

        if total_transactions_number > self.default_transactions_number:
            transactions_threshold_reached = False
            while (
                params['skip'] <= total_transactions_number
                or params['skip'] >= 20000  # Arbitrary limit if something goes wrong with total_transactions_number
            ):
                params['skip'] += self.default_transactions_number
                self.history_page.go(params=params)
                for transaction in iter_method(self.page):
                    if transaction.date < (date.today() - timedelta(days=self.history_maximum_days)):
                        transactions_threshold_reached = True
                        break
                    transactions_list.append(transaction)

                if transactions_threshold_reached:
                    # Do not uselessly do requests for transaction above 1 year old
                    # since it can take quite a while for some accounts.
                    break

        return transactions_list

    def _iter_card_history(self, account, is_coming=False):
        params = {
            'businessType': 'UserProfile',
            'accountIds': account._website_id,
            'parsedData': '[{"key":"transactionGranularityCode","value":"XT"}]',
            'skip': 0,
            'take': self.default_transactions_number,
            'includeDisabledAccounts': 'true',
            'ascendingOrder': 'false',
            'useAndSearchForParsedData': 'false',
        }
        if account.owner_type == AccountOwnerType.ORGANIZATION:
            params['businessType'] = 'BusinessProfile'

        self.history_page.go(params=params)

        if is_coming:
            return self.handle_pagination(params, self.history_page.klass.iter_card_coming)
        return self.handle_pagination(params, self.history_page.klass.iter_card_history)

    @need_login
    def iter_history(self, account):
        if account.type not in (
            Account.TYPE_CHECKING,
            Account.TYPE_SAVINGS,
            Account.TYPE_PEA,
            Account.TYPE_MARKET,
            Account.TYPE_LIFE_INSURANCE,
            Account.TYPE_CAPITALISATION,
            Account.TYPE_CARD,
            Account.TYPE_REVOLVING_CREDIT,
        ):
            # TODO Handle loans with a PSU account.
            self.logger.info('%s is not handled or has no history' % account.type)
            return []

        if account.type in (Account.TYPE_PEA, Account.TYPE_MARKET) and not account._is_cash_pea:
            if 'PARTS SOCIALES' in account.label:
                # TODO Investigate how to retrieve history
                self.logger.warning('"CPT PARTS SOCIALES" account to investigate')
                return []
            self.go_to_secondary_space('linebourse', account)
            history = self.linebourse.iter_history(account.id)
            self.leave_linebourse_space()
            return history

        elif account.type in (Account.TYPE_LIFE_INSURANCE, Account.TYPE_CAPITALISATION):
            self.go_to_secondary_space('extranet', account)
            self.life_insurance_history.go()
            return sorted_transactions(self.page.iter_history())

        elif account.type == Account.TYPE_CARD:
            return self._iter_card_history(account)

        elif account.type == Account.TYPE_REVOLVING_CREDIT:
            self.revolving_history.go(revolving_id=account.id)
            return self.page.iter_history()

        else:
            params = {
                'businessType': 'UserProfile',
                'accountIds': account._website_id,
                'parsedData': '[{"key":"transactionGranularityCode","value":"IN"},{"key":"transactionGranularityCode","value":"ST"}]',
                'skip': 0,
                # 'take': '50' -> default parameter for the number of transactions to be returned.
                # Response will contain 999 transactions if the param is not provided.
                # There is apparently no limit to the number of transactions that can be
                # returned for one call but sticking to the website behavior might avoid
                # triggering any alert system on BPCE's side.
                'take': self.default_transactions_number,
                'includeDisabledAccounts': 'true',
                'ascendingOrder': 'false',
                'orderBy': 'ByParsedData',
                'parsedDataNameToOrderBy': 'accountingDate',
                'useAndSearchForParsedData': 'false',
                # 'include': 'Merchant' -> Although the website always uses this parameter,
                # avoid it since it makes the JSON way bigger.
            }
            if account.owner_type == AccountOwnerType.ORGANIZATION:
                params['businessType'] = 'BusinessProfile'

            self.history_page.go(params=params)

            return self.handle_pagination(params, self.history_page.klass.iter_history)

    @need_login
    def iter_coming(self, account):
        if account.type not in (Account.TYPE_CARD, Account.TYPE_CHECKING):
            return []

        if account.type == Account.TYPE_CARD:
            return self._iter_card_history(account, is_coming=True)
        else:
            params = {
                'businessType': 'UserProfile',
                'paymentStatus': 'Open',
                'accountIds': account._website_id,
                'skip': 0,
                'includeDisabledAccounts': 'true',
                'transactionAccountingStatus': 'UP',
                'take': self.default_transactions_number,
            }

            if account.owner_type == AccountOwnerType.ORGANIZATION:
                params['businessType'] = 'BusinessProfile'

            self.accounts_coming.go(params=params)

            return self.handle_pagination(params, self.accounts_coming.klass.iter_coming)

    @need_login
    def iter_investments(self, account):
        if account.type in (Account.TYPE_PEA, Account.TYPE_MARKET) and not account._is_cash_pea:
            if account.label == 'CPT PARTS SOCIALES':
                # TODO Investigate how to retrieve investments
                self.logger.warning('"CPT PARTS SOCIALES" account to investigate')
                return
            self.go_to_secondary_space('linebourse', account)
            inv = self.linebourse.iter_investments(account.id)
            self.leave_linebourse_space()
            yield from inv

        elif account.type in (Account.TYPE_LIFE_INSURANCE, Account.TYPE_CAPITALISATION):
            self.go_to_secondary_space('extranet', account)
            self.life_insurance_investments.go()
            yield from self.page.iter_investment()

    @need_login
    def iter_subscriptions(self):
        self.subscription.go()
        yield self.page.get_subscription()

    @need_login
    def iter_documents(self, subscription):
        params = {
            'tache': 'EDOCEG',
            'contexte': 'DPW',
        }
        url = self.documents.build(params=params)
        id_token = jwt.get_unverified_claims(self.id_token)

        data = {
            'access_token': self.authorization_token,
            'ctx': 'typsrv=WE&sc=2&base_url=https%3A%2F%2Fwww.net444.caisse-epargne.fr%2F',
            'ctx_routage': '',
            'id_token': id_token,
            'redirectUrl': url,
        }
        self.location('https://www.net444.caisse-epargne.fr/loginbel.aspx', data=data)

        return self.page.iter_documents(subid=subscription.id)

    def download_document(self, document):
        return self.page.download(document).content
