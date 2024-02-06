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
from datetime import timedelta, datetime
from functools import wraps
from uuid import uuid4

from woob.browser import URL, need_login
from woob.browser.adapters import LowSecHTTPAdapter
from woob.browser.exceptions import ClientError, HTTPNotFound, ServerError
from woob.browser.mfa import TwoFactorBrowser
from woob.capabilities.bank import Account
from woob.capabilities.base import find_object
from woob.exceptions import (
    AppValidation, AppValidationExpired, AuthMethodNotImplemented, BrowserIncorrectPassword,
    BrowserUnavailable, OfflineOTPQuestion, OTPSentType, SentOTPQuestion,
)
from woob.capabilities.bank import Transaction
from woob.tools.date import now_as_utc
from woob.tools.misc import polling_loop
from woob_modules.caissedepargne.pages import VkImagePage

from .pages import (
    AppValidationPage,
    AuthenticationMethodPage, AuthenticationStepPage, AuthorizeErrorPage, AuthorizePage,
    BPOVirtKeyboard, ErrorPage, HomePage,
    InfoTokensPage, JsFilePage, JsFilePageEspaceClient, LastConnectPage, LoggedOut,
    LoginPage, LoginTokensPage,
    NewLoginPage, RedirectErrorPage, UnavailablePage, SynthesePage, TransactionPage,
)

__all__ = ['BanquePopulaire']


class BrokenPageError(Exception):
    pass


class TemporaryBrowserUnavailable(BrowserUnavailable):
    # To handle temporary errors that are usually solved just by making a retry
    pass


def retry(exc_check, tries=4):
    """Decorate a function to retry several times in case of exception.

    The decorated function is called at max 4 times. It is retried only when it
    raises an exception of the type `exc_check`.
    If the function call succeeds and returns an iterator, a wrapper to the
    iterator is returned. If iterating on the result raises an exception of type
    `exc_check`, the iterator is recreated by re-calling the function, but the
    values already yielded will not be re-yielded.
    For consistency, the function MUST always return values in the same order.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(browser, *args, **kwargs):
            def cb():
                return func(browser, *args, **kwargs)

            for i in range(tries, 0, -1):
                try:
                    ret = cb()
                except exc_check as exc:
                    browser.logger.debug('%s raised, retrying', exc)
                    continue

                if not (hasattr(ret, '__next__') or hasattr(ret, 'next')):
                    return ret  # simple value, no need to retry on items
                return iter_retry(cb, value=ret, remaining=i, exc_check=exc_check, logger=browser.logger)

            raise BrowserUnavailable('Site did not reply successfully after multiple tries')

        return wrapper
    return decorator


def no_need_login(func):
    # indicate a login is in progress, so LoggedOut should not be raised
    def wrapper(browser, *args, **kwargs):
        browser.no_login += 1
        try:
            return func(browser, *args, **kwargs)
        finally:
            browser.no_login -= 1

    return wrapper


class BanquePopulaireAccount(Account):
    def __init__(self):
        super().__init__()
        self._contractPfmId = None


class BanquePopulaire(TwoFactorBrowser):
    HTTP_ADAPTER_CLASS = LowSecHTTPAdapter

    TWOFA_DURATION = 90 * 24 * 60

    first_login_page = URL(r'/$')
    new_first_login_page = URL(r'/se-connecter/identifier')
    login_page = URL(r'https://[^/]+/auth/UI/Login.*', LoginPage)
    new_login = URL(r'https://www.banquepopulaire.fr/se-connecter/identifier', NewLoginPage)
    js_file = URL(r'https://[^/]+/.*se-connecter/main\..*.js$', JsFilePage)
    js_espaceclient_file = URL(r'https://[^/]+/.*espace-client/main\..*.js', JsFilePageEspaceClient)
    root_clientdashboard_page = URL(r'/espace-client/', NewLoginPage)
    authorize = URL(r'https://www.as-ex-ath-groupe.banquepopulaire.fr/api/oauth/v2/authorize', AuthorizePage)
    login_tokens = URL(r'https://www.as-ex-ath-groupe.banquepopulaire.fr/api/oauth/v2/consume', LoginTokensPage)
    info_tokens = URL(r'https://www.as-ex-ano-groupe.banquepopulaire.fr/api/oauth/v2/token', InfoTokensPage)

    authentication_step = URL(
        r'https://www.icgauth.banquepopulaire.fr/dacsrest/api/v1u0/transaction/(?P<validation_id>[^/]+)/step',
        AuthenticationStepPage
    )
    authentication_method_page = URL(
        r'https://www.icgauth.banquepopulaire.fr/dacsrest/api/v1u0/transaction/(?P<validation_id>)',
        AuthenticationMethodPage,
    )
    vk_image = URL(
        r'https://www.icgauth.banquepopulaire.fr/dacs-rest-media/api/v1u0/medias/mappings/[a-z0-9-]+/images',
        VkImagePage,
    )
    app_validation = URL(r'https://www.icgauth.banquepopulaire.fr/dacsrest/WaitingCallbackHandler', AppValidationPage)

    synthesis_views = URL(
        r'https://www.rs-ex-ath-groupe.banquepopulaire.fr/bapi/contract/v2/augmentedSynthesisViews',
        SynthesePage)

    transactions = URL(r'https://www.rs-ex-ath-groupe.banquepopulaire.fr/pfm/user/v1.1/transactions', TransactionPage)

    error_page = URL(
        r'https://[^/]+/cyber/internet/ContinueTask.do',
        r'https://[^/]+/_layouts/error.aspx',
        r'https://[^/]+/portailinternet/_layouts/Ibp.Cyi.Administration/RedirectPageError.aspx',
        ErrorPage
    )

    unavailable_page = URL(
        r'https://[^/]+/s3f-web/.*',
        r'https://[^/]+/static/errors/nondispo.html',
        r'/i-RIA/swc/1.0.0/desktop/index.html',
        UnavailablePage
    )

    authorize_error = URL(r'https://[^/]+/dacswebssoissuer/AuthnRequestServlet', AuthorizeErrorPage)

    redirect_error_page = URL(
        r'https://[^/]+/portailinternet/?$',
        RedirectErrorPage
    )

    home_page = URL(
        r'https://[^/]+/.*espace-client',
        HomePage
    )

    last_connect = URL(
        r'https://www.rs-ex-ath-groupe.banquepopulaire.fr/bapi/user/v1/user/lastConnect',
        LastConnectPage
    )

    redirect_uri = URL(r'https://www.ibps.bpgo.banquepopulaire.fr/callbackleg')

    HAS_CREDENTIALS_ONLY = True

    def __init__(self, website, config, *args, **kwargs):
        self.config = config
        super(BanquePopulaire, self).__init__(
            self.config, self.config['login'].get(), self.config['password'].get(), *args, **kwargs
        )
        self.BASEURL = 'https://%s' % website
        self.validation_id = None
        self.mfa_validation_data = None
        self.user_type = None
        self.cdetab = self.config['cdetab'].get()
        self.continue_url = None
        self.term_id = None
        self.access_token = None
        self.access_token_expire = None
        self.redirect_url = 'https://www.icgauth.banquepopulaire.fr/dacsrest/api/v1u0/transaction/'
        self.token = None

        self.documents_headers = None

        self.AUTHENTICATION_METHODS = {
            'code_sms': self.handle_sms,
            'code_emv': self.handle_emv,
            'resume': self.handle_cloudcard,
        }

        self.__states__ += (
            'validation_id',
            'mfa_validation_data',
            'user_type',
            'cdetab',
            'continue_url',
            'term_id',
            'user_code',
            'access_token',
            'access_token_expire',
        )

    def deinit(self):
        super(BanquePopulaire, self).deinit()

    no_login = 0

    def load_state(self, state):
        if state.get('validation_unit'):
            # If starting in the middle of a 2FA, and calling for a new authentication_method_page,
            # we'll lose validation_unit validity.
            state.pop('url', None)
        super(BanquePopulaire, self).load_state(state)

    def locate_browser(self, state):
        super(BanquePopulaire, self).locate_browser(state)

    def init_login(self):
        if self.isSSOBearerValid():
            return

        if (
            self.twofa_logged_date and (
                now_as_utc() > (self.twofa_logged_date + timedelta(minutes=self.TWOFA_DURATION))
            )
        ):
            # Since we doing a PUT at every login, we assume that the 2FA of banquepopulaire as no duration
            # Reseting after 90 days because of legal concerns
            self.term_id = None

        if not self.term_id:
            # The term_id is the terminal id
            # It bounds a terminal to a valid two factor authentication
            # If not present, we are generating one
            self.term_id = str(uuid4())

        try:
            self.new_first_login_page.go()
        except (ClientError, HTTPNotFound) as e:
            if e.response.status_code in (403, 404):
                # Sometimes the website makes some redirections that leads
                # to a 404 or a 403 when we try to access the BASEURL
                # (website is not stable).
                raise BrowserUnavailable(str(e))
            raise

        # avoids trying to relog in while it's already on home page
        if self.home_page.is_here():
            return

        if self.new_login.is_here():
            self.do_new_login()

        if self.authentication_step.is_here():
            # We are successfully logged in with a 2FA still valid
            if self.page.is_authentication_successful():
                self.validation_id = None  # Don't want an old validation_id in storage.
                self.finalize_login()
                return

            self.page.check_errors(feature='login')

            auth_method = self.page.get_authentication_method_type()
            self._set_mfa_validation_data()

            if auth_method == 'SMS':
                phone_number = self.page.get_phone_number()
                raise SentOTPQuestion(
                    'code_sms',
                    medium_type=OTPSentType.SMS,
                    message='Veuillez entrer le code reçu au numéro %s' % phone_number,
                )
            elif auth_method == 'CLOUDCARD':
                # At that point notification has already been sent, although
                # the website displays a button to chose another auth method.
                devices = self.page.get_devices()
                if not len(devices):
                    raise AssertionError('Found no device, please audit')
                if len(devices) > 1:
                    raise AssertionError('Found several devices, please audit to implement choice')

                # name given at the time of device enrolling done in the bank's app, empty name is not allowed
                device_name = devices[0]['friendlyName']

                # Time seen and tested: 540" = 9'.
                # At the end of that duration, we can still validate in the app, but a message is then displayed: "Opération déjà refusée".
                # In a navigator, website displays "Votre session a expiré" and propose to log in again.
                expires_at = now_as_utc() + timedelta(seconds=self.page.get_time_left())
                raise AppValidation(
                    message=f"Prenez votre téléphone «{device_name}»."
                    + " Ouvrez votre application mobile."
                    + " Saisissez votre code Sécur'Pass sur le téléphone,"
                    + " ou utilisez votre identification biométrique.",
                    expires_at=expires_at,
                    medium_label=device_name,
                )
            else:
                raise AssertionError('Unhandled authentication method: %s' % auth_method)
        raise AssertionError('Did not encounter authentication_step page after performing the login')

    def handle_2fa_otp(self, otp_type):
        # It will occur when states become obsolete
        if not self.mfa_validation_data:
            raise BrowserIncorrectPassword('Le délai pour saisir le code a expiré, veuillez recommencer')

        data = {
            'validate': {
                self.mfa_validation_data['validation_unit_id']: [{
                    'id': self.mfa_validation_data['id'],
                }],
            },
        }

        data_otp = data['validate'][self.mfa_validation_data['validation_unit_id']][0]
        data_otp['type'] = otp_type
        if otp_type == 'SMS':
            data_otp['otp_sms'] = self.code_sms
        elif otp_type == 'EMV':
            data_otp['token'] = self.code_emv

        try:
            self.authentication_step.go(
                validation_id=self.validation_id,
                json=data
            )
        except (ClientError, ServerError) as e:
            if (
                # "Session Expired" seems to be a 500, this is strange because other OTP errors are 400
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

        self.mfa_validation_data = None

        authentication_status = self.page.authentication_status()
        if authentication_status == 'AUTHENTICATION_SUCCESS':
            self.validation_id = None  # Don't want an old validation_id in storage.
            self.finalize_login()
        else:
            self.page.login_errors(authentication_status, otp_type=otp_type)

    def handle_sms(self):
        self.handle_2fa_otp(otp_type='SMS')

    def handle_emv(self):
        self.handle_2fa_otp(otp_type='EMV')

    def handle_cloudcard(self, **params):
        assert self.mfa_validation_data

        for _ in polling_loop(timeout=300, delay=5):
            self.app_validation.go()
            status = self.page.get_status()

            # The status is 'valid' even for non success authentication
            # But authentication status is checked in authentication_step response.
            # Ex: when the user refuses the authentication on the application, AUTHENTICATION_CANCELED is returned.
            if status == 'valid':
                self.authentication_step.go(
                    validation_id=self.validation_id,
                    json={
                        'validate': {
                            self.mfa_validation_data['validation_unit_id']: [{
                                'id': self.mfa_validation_data['id'],
                                'type': 'CLOUDCARD',
                            }],
                        },
                    },
                )
                authentication_status = self.page.authentication_status()
                if authentication_status == 'AUTHENTICATION_SUCCESS':
                    self.finalize_login()
                    self.validation_id = None
                    self.mfa_validation_data = None
                    break
                else:
                    self.page.check_errors(feature='login')

            assert status == 'progress', 'Unhandled CloudCard status : "%s"' % status

        else:
            self.validation_id = None
            self.mfa_validation_data = None
            raise AppValidationExpired()

    def get_bpcesta_Auth(self):
        return {
            'csid': str(uuid4()),
            'typ_app': 'rest',
            'enseigne': 'bp',
            'typ_sp': 'out-band',
            'typ_act': 'auth',
            'snid': '678256',
            'cdetab': self.cdetab,
            'typ_srv': 'part',
            "phase": "",
            'term_id': self.term_id,
        }

    def get_bpcesta_SSO(self):
        return {
            'cdetab': self.cdetab,
            'enseigne': 'bp',
            'login_hint': self.user_code,
            'typ_srv': 'part',
            'typ_sp': 'out-band',
            'typ_app': 'rest',
            'typ_act': 'sso',
        }

    def _set_mfa_validation_data(self):
        """Same as in caissedepargne."""
        self.mfa_validation_data = self.page.get_authentication_method_info()
        self.mfa_validation_data['validation_unit_id'] = self.page.validation_unit_id

    # need to try from the top in that case because this login is a long chain of redirections
    @retry(TemporaryBrowserUnavailable)
    def do_new_login(self):
        main_js_file = self.page.get_main_js_file_url()
        self.location(main_js_file)

        client_id = self.page.get_client_id()
        nonce = str(uuid4())  # Not found anymore

        data = {
            'grant_type': 'client_credentials',
            'client_id': self.page.get_user_info_client_id(),
            'scope': '',
        }

        self.info_tokens.go(data=data)

        self.user_code = self.config['login'].get()

        bpcesta = self.get_bpcesta_Auth()

        claims = {
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
                'auth_time': {
                    'essential': True,
                },
                'last_login': None,
                'cdetab': None,
                'pro': None,
            },
        }

        params = {
            'cdetab': self.cdetab,
            'client_id': client_id,
            'response_type': 'id_token token',
            'nonce': nonce,
            'response_mode': 'form_post',
            'redirect_uri': self.redirect_uri.build(),
            'claims': json.dumps(claims),
            'bpcesta': json.dumps(bpcesta),
            'login_hint': self.user_code,
            'display': 'page',
        }
        headers = {
            'Accept': 'application/json, text/plain, */*',  # Mandatory, else you've got an HTML page.
            'Content-Type': 'application/x-www-form-urlencoded',
            'Content-Length': '0',  # Mandatory, otherwhise enjoy the 415 error
        }

        self.authorize.go(params=params, method='POST', headers=headers)

        headers = {
            'Accept': 'application/json, text/plain, */*',  # Mandatory, else you've got an HTML page.
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'https://www.banquepopulaire.fr/se-connecter/identifier(redirect:authentifier)',  # Mandatory if not, you have 430 error
        }
        self.do_redirect('SAMLRequest', headers=headers)
        self.validation_id = self.page.get_validation_id()

        security_level = self.page.get_security_level()
        is_sca_expected = self.page.is_sca_expected()

        # It means we are going to encounter an SCA
        if is_sca_expected:
            self.check_interactive()

        auth_method = self.check_for_fallback()
        if auth_method == 'CERTIFICATE':
            raise AuthMethodNotImplemented("La méthode d'authentification par certificat n'est pas gérée")
        elif auth_method == 'EMV':
            # This auth method replaces the sequence PASSWORD+SMS.
            # So we are on authentication_method_page.
            self._set_mfa_validation_data()
            raise OfflineOTPQuestion(
                'code_emv',
                message='Veuillez renseigner le code affiché sur le boitier (Pass Cyberplus en mode « Code »)',
            )

        if self.authorize_error.is_here():
            raise BrowserUnavailable(self.page.get_error_message())
        self.page.check_errors(feature='login')
        validation_unit = self.page.validation_unit_id

        vk_info = self.page.get_authentication_method_info()
        vk_id = vk_info['id']

        if vk_info.get('virtualKeyboard') is None:
            # no VK, password to submit
            code = self.password
        else:
            if not self.password.isnumeric():
                raise BrowserIncorrectPassword('Le mot de passe doit être composé de chiffres uniquement')

            vk_images_url = vk_info['virtualKeyboard']['externalRestMediaApiUrl']

            self.location(vk_images_url)
            images_url = self.page.get_all_images_data()
            vk = BPOVirtKeyboard(self, images_url)
            code = vk.get_string_code(self.password)

        headers = {
            'Referer': self.BASEURL,
            'Accept': 'application/json, text/plain, */*',
        }

        self.authentication_step.go(
            validation_id=self.validation_id,
            json={
                'validate': {
                    validation_unit: [{
                        'id': vk_id,
                        'password': code,
                        'type': 'PASSWORD',
                    }],
                },
            },
            headers=headers,
        )

        if self.authentication_step.is_here():
            status = self.page.get_status()
            if status == 'AUTHENTICATION_SUCCESS':
                self.logger.warning("Security level %s is not linked to an SCA", security_level)
            elif status == 'AUTHENTICATION':
                auth_method = self.page.get_authentication_method_type()
                if auth_method:
                    self.logger.warning(
                        "Security level %s is linked to an SCA with %s auth method",
                        security_level, auth_method
                    )
            else:
                self.logger.warning(
                    "Encounter %s security level without authentication success and any auth method",
                    security_level
                )

    @retry(BrokenPageError, tries=2)
    def handle_continue_url(self):
        # continueURL not found in HAR
        params = {
            'Segment': self.user_type,
            'NameId': self.user_code,
            'cdetab': self.cdetab,
            'continueURL': '/cyber/ibp/ate/portal/internet89C3Portal.jsp?taskId=aUniversAccueilRefonte',
        }

        self.location(self.continue_url, params=params)
        if self.response.status_code == 302:
            # No redirection to the next url
            # Let's do the job instead of the bank
            self.location('/portailinternet')

        if self.new_login.is_here():
            # Sometimes, we land on the wrong page. If we retry, it usually works.
            raise BrokenPageError()

    def finalize_login(self):
        headers = {
            'Referer': self.BASEURL,
            'Accept': 'application/json, text/plain, */*',
        }

        self.page.check_errors(feature='login')
        self.do_redirect('SAMLResponse', headers)

        self.put_terminal_id()

    def check_for_fallback(self):
        for _ in range(3):
            current_method = self.page.get_authentication_method_type()
            if self.page.is_other_authentication_method() and current_method != 'PASSWORD':
                # we might first have a CERTIFICATE method, which we may fall back to EMV,
                # which we may fall back to PASSWORD
                self.authentication_step.go(
                    validation_id=self.validation_id,
                    json={'fallback': {}},
                )
            else:
                break
        return current_method

    def do_redirect(self, keyword, headers=None):
        if headers is None:
            headers = {}

        # During the second do_redirect
        # The AuthenticationMethodPage carries a status response
        # This status can be different from AUTHENTICATION_SUCCESS
        # Even if the do_new_login flow went well
        # (Yes, even if the status response in do_new_login was AUTHENTICATION_SUCCESS.....)

        if self.authentication_method_page.is_here():
            self.page.check_errors(feature='login')
        next_url = self.page.get_next_url()
        payload = self.page.get_payload()
        self.location(next_url, data={keyword: payload}, headers=headers)

        if self.login_tokens.is_here():
            self.access_token = self.page.get_access_token()

            if self.access_token is None:
                raise AssertionError('Did not obtain the access_token mandatory to finalize the login')

        if self.redirect_error_page.is_here() and self.page.is_unavailable():
            # website randomly unavailable, need to retry login from the beginning
            self.do_logout()  # will delete cookies, or we'll always be redirected here
            self.location(self.BASEURL)
            raise TemporaryBrowserUnavailable()

    def put_terminal_id(self):
        # This request is mandatory.
        # We assume it associates the current terminal_id,
        # generate at the beginning of the login,
        # to the SCA that has been validated.
        # Presenting this terminal_id for further login
        # will avoid triggering another SCA.

        # This request occurs at every login on
        # banquepopulaire website
        # To ensure consistency, we are doing so.
        self.last_connect.go(
            method='PUT',
            headers={
                'Authorization': 'Bearer %s' % self.access_token,
                'X-Id-Terminal': self.term_id,
            },
            json={}
        )

    def isSSOBearerValid(self):
        if (self.access_token_expire is None):
            self.logger.debug('No valid token found in local storage')
            return False

        expire_dt = datetime.strptime(self.access_token_expire, "%m/%d/%Y %H:%M:%S")

        current_dt = datetime.now()
        expected_endofrequests_dt = current_dt + timedelta(seconds=20)

        if (expire_dt < expected_endofrequests_dt):
            self.logger.debug('Token found in local storage, but expired')
            return False

        self.logger.debug('Valid token found in local storage, skip login')
        return True

    def saveSSOBearer(self, token, expire):
        current_dt = datetime.now()
        expire_dt = current_dt + timedelta(seconds=int(expire))
        self.access_token_expire = expire_dt.strftime("%m/%d/%Y %H:%M:%S")
        self.access_token = token

    def updateBearerForDataConsumptionIfNeeded(self):
        if self.isSSOBearerValid():
            return

        self.root_clientdashboard_page.go()
        main_js_file = self.page.get_main_js_file_url()
        self.location(main_js_file)
        client_id = self.page.get_client_id()

        data = {
            'grant_type': 'client_credentials',
            'client_id': self.page.get_user_info_client_id(),
            'scope': 'readTypology readAgencyV2',
        }
        self.info_tokens.go(data=data)

        bpcesta = self.get_bpcesta_SSO()
        claims = {
            'id_token': {
                'cdetab': None,
                'pro': None,
            },
            'userinfo':
            {
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
        }
        params = {
            'cdetab': self.cdetab,
            'client_id': client_id,
            'response_type': 'id_token token',
            'nonce': str(uuid4()),
            'response_mode': 'form_post',
            'claims': json.dumps(claims),
            'bpcesta': json.dumps(bpcesta),
            'login_hint': self.user_code,
            'display': 'page',
        }
        headers = {
            'Accept': 'application/json, text/plain, */*',  # Mandatory, else you've got an HTML page.
            'Content-Type': 'application/x-www-form-urlencoded',
            'Content-Length': '0',  # Mandatory, otherwhise enjoy the 415 error
            'Origin': 'https://www.banquepopulaire.fr',
            'Referer': 'https://www.banquepopulaire.fr/',
        }
        self.authorize.go(params=params, method='POST', headers=headers)

#       Authorize response gave a SAML request in the payload
#       Play it by "do_redirect" will give us a json with a samlResponse and the response consumer :
#       {
#           "id":"blahblah",
#           "locale":"en",
#           "response":{
#               "status":"AUTHENTICATION_SUCCESS",
#               "saml2_post":{
#                   "samlResponse":"a very hug lot of blah blah, probably in base64, but we don't really care",
#                   "action":"https://www.as-ex-ath-groupe.banquepopulaire.fr/api/oauth/v2/consume",
#                   "method":"POST"
#               }
#           }
#       }
        headers = {
            'Accept': 'application/json, text/plain, */*',  # Mandatory, else you've got an HTML page.
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': 'https://www.banquepopulaire.fr/se-connecter/identifier(redirect:authentifier)',  # Mandatory if not, you have 430 error
        }
        self.do_redirect('SAMLRequest', headers=headers)

#       Last but not least, we have to call the v2/consume with the SAML Response and that will provide us the wanted Token in json:
#       ##{
#       ##    "method" : "POST",
#       ##    "enctype" : "application/x-www-form-urlencoded",
#       ##    "action" : "https://www.banquepopulaire.fr/espace-client/implicit/callback",
#       ##    "parameters" : {
#       ##        "access_token" : "0Ylr9f5RxYGBQCAeOxh2....."
        self.do_redirect('SAMLResponse', headers=headers)

#       ## Wonderfull in this json we have the acces_token mandatory to reach user data (like balances)
        self.saveSSOBearer(token=self.page.get_access_token(), expire=self.page.get_access_expire())
        self.access_token = self.page.get_access_token()

    @retry(LoggedOut)
    @need_login
    def iter_accounts(self, get_iban=False):
        self.updateBearerForDataConsumptionIfNeeded()

        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Authorization': 'Bearer %s' % self.access_token,
            'Origin': 'https://www.banquepopulaire.fr',
            'Referer': 'https://www.banquepopulaire.fr/',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        }
#       This is a new API. I still don't know how is built the field productFamilyPFM=1,2,3,4,6,7,17,18.
#       Let see with other users if they have the same IDs and, if necessary, how to dynamically retrieve it...
        self.location(
            'https://www.rs-ex-ath-groupe.banquepopulaire.fr/bapi/contract/v2/augmentedSynthesisViews?productFamilyPFM=1,2,3,4,6,7,17,18&pfmCharacteristicsIndicator=true',
            headers=headers)
        raw_json_data = self.page.get_raw_json()
        accounts_data = json.loads(raw_json_data)
        accounts = []

        if "items" in accounts_data:
            for element in accounts_data["items"]:
                account = BanquePopulaireAccount()
                if element is not None and "identification" in element:
                    identification = element["identification"]
                    if identification is not None and "augmentedSynthesisViewId" in identification:
                        augmentedSynthesisViewId = identification["augmentedSynthesisViewId"]
                        if augmentedSynthesisViewId is not None and "id" in augmentedSynthesisViewId:
                            account.id = augmentedSynthesisViewId["id"]
                        else:
                            self.logger.warning("Miss /items/**/identification/augmentedSynthesisViewId/id key in one account provided by the bank : entry skipped")
                            continue
                        if "contractPfmId" in identification:
                            account._contractPfmId = identification["contractPfmId"]
                    else:
                        self.logger.warning("Miss /items/**/identification/augmentedSynthesisViewId key in one account provided by the bank : entry skipped")
                        continue
                else:
                    self.logger.warning("Miss /items/**/identification/ key in one account provided by the bank : entry skipped")
                    continue

                if element is not None and "identity" in element:
                    identity = element["identity"]
                    if (identity is not None and "bankingClientLabel" in identity and "balance" in identity
                            and "contractLabel" in identity):
                        account.label = ('%s %s' % (identity["contractLabel"], identity["bankingClientLabel"])).strip()

                        balance = identity["balance"]
                        if balance is not None and "value" in balance and "currencyCode" in balance:
                            account.balance = balance["value"]
                            account.currency = balance["currencyCode"]
                        else:
                            self.logger.warning("Miss /items/**/identity/balance/value or /items/**/identity/balance/currencyCode key in one account provided by the bank : entry skipped")
                            continue

                        account._prev_debit = None
                        account._next_debit = None
                        account._params = None
                        account._coming_params = None
                        account._coming_count = None
                        account._invest_params = None
                        account._loan_params = None
                    else:
                        self.logger.warning("Miss /items/**/identity/bankingClientLabel or /items/**/identity/balance or /items/**/identity/contractLabel key in one account provided by the bank : entry skipped")
                else:
                    self.logger.warning("Miss /items/**/identity key in one account provided by the bank : entry skipped")

                accounts.append(account)

        else:
            self.logger.warning("Miss /items/ in accounts provided by the bank : couldn't do anything...")
#       No Yield here, no more account to process
        return accounts

    @retry(LoggedOut)
    @need_login
    def get_account(self, id):
        return find_object(self.iter_accounts(get_iban=False), id=id)

    @retry(LoggedOut)
    @need_login
    def iter_history(self, account: BanquePopulaireAccount, coming=False):
        self.updateBearerForDataConsumptionIfNeeded()
        pagination_start = 0
        pagination_count = 25
        current_skip_value = pagination_start

        transactions = []

        while True:
            params = {
                'businessType': 'UserProfile',
                'accountIds': str(account._contractPfmId),
                'include': 'Merchant',
                'parsedData': '[{"key":"transactionGranularityCode","value":"IN"},{"key":"transactionGranularityCode","value":"ST"}]',
                'skip': current_skip_value,
                'take': pagination_count,
                'includeDisabledAccounts': 'true',
                'ascendingOrder': 'false',
                'orderBy': 'ByParsedData',
                'parsedDataNameToOrderBy': 'accountingDate',
                'useAndSearchForParsedData': 'false',
            }
            headers = {
                'Accept': 'application/json, text/plain, */*',  # Mandatory, else you've got an HTML page.
                'Authorization': 'Bearer %s' % self.access_token,
                'Origin': 'https://www.banquepopulaire.fr',
                'Referer': 'https://www.banquepopulaire.fr/',
                'Host': 'www.rs-ex-ath-groupe.banquepopulaire.fr',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-site',
            }

            self.transactions.go(params=params, method='GET', headers=headers)
            raw_json_data = self.page.get_raw_json()
            transactions_data = json.loads(raw_json_data)

            for element in transactions_data['data']:
                transaction = Transaction()
                transaction.date = datetime.strptime(element['date'], '%Y-%m-%dT%H:%M:%S')
                transaction.label = element['text']
                if "parsedData" in element:
                    parsedData = element["parsedData"]
                    if "label1" in parsedData:
                        transaction.label += " - "
                        transaction.label += parsedData["label1"]
                    if "label2" in parsedData:
                        transaction.label += " - "
                        transaction.label += parsedData["label2"]
                    if "label3" in parsedData:
                        transaction.label += " - "
                        transaction.label += parsedData["label3"]

                transaction.amount = element['amount']
#               transaction.category  ####Must be done with a correlation with json content of www.rs-ex-ath-groupe.banquepopulaire.fr/pfm/user/v1.1/categories

                transactions.append(transaction)
                yield transaction

            current_skip_value += pagination_count
        return transactions


class iter_retry(object):
    # when the callback is retried, it will create a new iterator, but we may already yielded
    # some values, so we need to keep track of them and seek in the middle of the iterator

    def __init__(self, cb, remaining=4, value=None, exc_check=Exception, logger=None):
        self.cb = cb
        self.it = value
        self.items = []
        self.remaining = remaining
        self.exc_check = exc_check
        self.logger = logger

    def __iter__(self):
        return self

    def __next__(self):
        if self.remaining <= 0:
            raise BrowserUnavailable('Site did not reply successfully after multiple tries')

        if self.it is None:
            self.it = self.cb()

            # recreated iterator, consume previous items
            try:
                nb = -1
                for sent in self.items:
                    new = next(self.it)
                    if hasattr(new, 'to_dict'):
                        equal = sent.to_dict() == new.to_dict()
                    else:
                        equal = sent == new
                    if not equal:
                        # safety is not guaranteed
                        raise BrowserUnavailable('Site replied inconsistently between retries, %r vs %r', sent, new)
            except StopIteration:
                raise BrowserUnavailable(
                    'Site replied fewer elements (%d) than last iteration (%d)', nb + 1, len(self.items)
                )
            except self.exc_check as exc:
                if self.logger:
                    self.logger.info('%s raised, retrying', exc)
                self.it = None
                self.remaining -= 1
                return next(self)

        # return one item
        try:
            obj = next(self.it)
        except self.exc_check as exc:
            if self.logger:
                self.logger.info('%s raised, retrying', exc)
            self.it = None
            self.remaining -= 1
            return next(self)
        else:
            self.items.append(obj)
            return obj

    next = __next__
