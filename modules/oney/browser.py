# -*- coding: utf-8 -*-

# Copyright(C) 2014 Budget Insight
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

import re
import time
from datetime import datetime
from urllib.parse import quote, urlparse

from requests.exceptions import HTTPError, TooManyRedirects, ConnectionError, ReadTimeout

from woob.capabilities.bank import Account
from woob.exceptions import (
    BrowserIncorrectPassword, BrowserPasswordExpired,
    AuthMethodNotImplemented, BrowserUnavailable,
    BrowserQuestion, ActionNeeded, AppValidation,
    AppValidationExpired,
)
from woob.browser import TwoFactorBrowser, URL, need_login
from woob.tools.value import Value

from .pages import (
    LoginPage, ClientPage, OperationsPage, ChoicePage,
    ContextInitPage, SendUsernamePage, SendCompleteStepPage, ClientSpacePage,
    OtherDashboardPage, OAuthPage, AccountsPage, JWTTokenPage, OtherOperationsPage,
    SendRiskEvaluationPage, SendInitStepPage,
)

__all__ = ['OneyBrowser']


class OneyBrowser(TwoFactorBrowser):
    BASEURL = 'https://www.oney.fr'
    LOGINURL = 'https://login.oney.fr'
    OTHERURL = 'https://middle.mobile.oney.io'

    home_login = URL(
        OTHERURL + r'/security/strongauth/authenticationcontext',
        LOGINURL + r'/context',  # Target of the redirection when going on the first URL
        LoginPage
    )

    # Login api
    context_init = URL(LOGINURL + r'/middle/context', ContextInitPage)
    send_risk_evaluation = URL(LOGINURL + r'/middle/riskevaluation', SendRiskEvaluationPage)
    send_username = URL(LOGINURL + r'/middle/initauthenticationflow', SendUsernamePage)
    send_init_step = URL(LOGINURL + r'/middle/initstep', SendInitStepPage)
    send_complete_step = URL(LOGINURL + r'/middle/completestrongauthenticationflow', SendCompleteStepPage)
    new_access_code = URL(LOGINURL + r'/middle/check_token')

    # Space selection
    choice = URL(r'/site/s/multimarque/choixsite.html', ChoicePage)
    choice_portal = URL(r'/site/s/login/loginidentifiant.html')

    # Oney space
    client = URL(r'/oney/client', ClientPage)
    client_space = URL(r'https://www.compte.oney.fr/espace-client/historique-facilypay', ClientSpacePage)
    operations = URL(r'/oney/client', OperationsPage)
    card_page = URL(r'/oney/client\?task=Synthese&process=SyntheseMultiCompte&indexSelectionne=(?P<acc_num>\d+)')

    # Other space
    dashboard = URL(r'https://espaceclient.oney.fr/dashboard', OtherDashboardPage)
    jwt_token_page = URL(OTHERURL + r'/JWTToken', JWTTokenPage)
    oauth = URL(OTHERURL + r'/web/login/oauth', OAuthPage)
    other_accounts = URL(OTHERURL + r'/web/dashboard', AccountsPage)
    other_operations = URL(OTHERURL + r'/web/operation/operations', OtherOperationsPage)

    has_oney = False
    has_other = False
    card_name = None
    is_mail = False
    pristine_params_headers = {
        'Environment': 'PRD',
        'Origin': 'Web',
        'IsLoggedIn': False,
    }
    params_headers = pristine_params_headers.copy()

    HAS_CREDENTIALS_ONLY = True

    def __init__(self, config, *args, **kwargs):
        super(OneyBrowser, self).__init__(config, config['login'].get(), config['password'].get(), *args, **kwargs)

        self.login_steps = None
        self.login_flow_id = None
        self.login_success_url = None
        self.login_customer_session_id = None
        self.login_additional_inputs = None
        self.login_client_id = None
        self.jwt_token = None
        self.__states__ += (
            'login_steps',
            'login_flow_id',
            'login_success_url',
            'login_customer_session_id',
            'login_additional_inputs',
            'login_client_id',
            'jwt_token',
        )

        self.AUTHENTICATION_METHODS = {
            'code': self.handle_phone_otp,
            'resume': self.handle_polling,
        }
        self.known_step_type = ('EMAIL_PASSWORD', 'IAD_ACCESS_CODE', 'SCA_PUSH', 'PHONE_OTP')

    def locate_browser(self, state):
        url = state['url']
        if self.BASEURL in url:
            try:
                self.location(url, params=self.other_space_params_headers())
            except (HTTPError, TooManyRedirects):
                pass
        else:
            super(OneyBrowser, self).locate_browser(state)

    def load_state(self, state):
        super(OneyBrowser, self).load_state(state)

        if self.login_client_id:
            self.session.headers.update({'Client-id': self.login_client_id})

    def dump_state(self):
        state = super(OneyBrowser, self).dump_state()
        if self.send_init_step.is_here():
            # We do not want to try to reload this page.
            state.pop('url', None)
        return state

    def clear_init_cookies(self):
        # Keep the device-id to prevent an SCA
        for cookie in self.session.cookies:
            if cookie.name == 'did_proxy':
                did_proxy = cookie
                break
        else:
            did_proxy = None
        self.session.cookies.clear()
        if did_proxy:
            self.session.cookies.set_cookie(did_proxy)

    @property
    def device_proxy_id(self):
        duration = 1800000  # Milliseconds (from proxyid script below)
        proxy_id = self.session.cookies.get('did_proxy', domain='login.oney.fr')

        if not proxy_id:
            text = self.open('https://argus.arcot.com/scripts/proxyid.js').text
            match = re.search(r'"(.+)"', text)
            if match:
                proxy_id = match.group(1)
            else:
                raise AssertionError('Could not retrieve a new device proxy id')

        # Cannot use datetime.timestamp since it is not in python2
        expires = int((datetime.now() - datetime(1970, 1, 1)).total_seconds() * 1000 + duration)
        self.session.cookies.set(name='did_proxy', value=proxy_id, domain='login.oney.fr', path='/', expires=expires)

        return proxy_id

    def send_fingerprint(self):
        ddna_arcot = (
            '{"VERSION":"2.1","MFP":{"Browser":{"UserAgent":"%s","Vendor":"","VendorSubID":"","BuildID":"20181001000000","CookieEnabled":true},"IEPlugins":{},"NetscapePlugins":{},"Screen":{"FullHeight":1080,"AvlHeight":1053,"FullWidth":1920,"AvlWidth":1920,"ColorDepth":24,"PixelDepth":24},"System":{"Platform":"Linux x86_64","OSCPU":"Linux x86_64","systemLanguage":"en-US","Timezone":0}},"ExternalIP":""}'
            % self.session.headers['User-Agent']
        )
        params = {
            'did_proxy': self.device_proxy_id,
            'ddna_arcot': quote(ddna_arcot),
            'ddna_arcot_time': '{"browser":0,"clientcaps":1,"plugin":0,"screen":4,"system":0,"boundingbox":2,"timetaken":7}',
        }

        self.open('https://argus.arcot.com/img/zero.png', params=params)

    def init_login(self):
        self.reset_session_for_new_auth()
        self.setup_headers_login()
        self.home_login.go(json={
            'header': {
                'origin': 'Web',
                'environment': 'PRD',
                'isLoggedIn': 'false',
            },
            'context': '',
            'successParams': '',
            'failParams': '',
        })
        context_token = self.page.get_context_token()
        assert context_token is not None, 'Should not have context_token=None'

        self.context_init.go(params={'contextToken': context_token})
        self.assert_no_error()
        self.login_customer_session_id = self.page.get_customer_session_id()
        self.login_client_id = self.page.get_client_id()
        oauth_token = self.page.get_oauth_token()
        self.login_success_url = self.page.get_success_url()
        self.login_additional_inputs = self.page.get_additionnal_inputs()

        self.send_fingerprint()

        self.session.headers.update({'Client-id': self.login_client_id})

        # There is a VK on the website but it does not encode the password
        if '@' in self.username:
            auth_type = 'EML'
            self.is_mail = True
        else:
            auth_type = 'IAD'

        digital_identity_selector = {
            'value': self.username,
            'type': 'authentication_factor',
            'subtype': auth_type,
        }

        self.send_risk_evaluation.go(json={
            'digital_identity_selector': digital_identity_selector,
            'oauth': oauth_token,
            'device_proxy_id': self.device_proxy_id,
            'x_ca_sessionid': self.login_customer_session_id,
            'service_id': 'LOGIN',
            'client_id': self.login_client_id,
        })
        self.assert_no_error()

        self.login_flow_id = self.page.get_flow_id()
        niveau_authent = self.page.get_niveau_authent()

        if niveau_authent == 'O':
            # Never seen in the wild but apparently if you
            # receive this code, you are already logged and
            # only need to use the oauth_token
            # Found by reverse engineering the website code
            assert oauth_token is not None
            self.finish_auth_with_token(oauth_token)
            return
        elif niveau_authent == 'D':
            # Message depuis translation.json:
            # Pour des raisons de sécurité, l’opération n’a pas pu aboutir.
            # Veuillez réessayez ultérieurement.
            raise BrowserUnavailable()
        elif niveau_authent in ['LIGHT', 'STRONG']:
            pass
        else:
            raise AssertionError('Niveau d\'authentification inconnu. %s' % niveau_authent)

        self.send_username.go(json={
            'digital_identity_selector': digital_identity_selector,
            'oauth': oauth_token,
            'flowid': self.login_flow_id,
            'service_id': None,
            'client_id': None,
            'authentication_type': None,
            'x_ca_sessionid': None,
        })
        self.assert_no_error()

        self.login_steps = self.page.get_steps()
        self.execute_login_steps()

    def execute_login_steps(self, token=None):
        # The website gives us a authentification plan during the login process.
        # We store this plan in the self.login_steps list.
        # In this method, we execute the plan step by step until we get
        # a login token or there is no more step to follow.

        # Each step has three attribute at each point in time.
        # - Type: What authentification challenge to do? Password, sms, etc
        #         You can find the complete list of supported type in self.known_step_type
        # - Action: What is the next action to do for that authentification challenge?
        #           Possible values: INIT, COMPLETE, DONE
        #           Init: Send the challenge to the user. (Ex: send the sms)
        #           Complete: Send the response to Oney. (Ex: send the password or the sms code)
        #           Done: When the step is finished.
        #           Some step type (ex: password) do not have a INIT action.
        # - Status: Is the step optional?
        #           Values: TODO, OPTIONAL, DONE
        #           Todo: Required step.
        #           Optional: we directly skip optional step.
        #           Done: When the step is finished.

        # An authentification without SCA has 1 step to send the password.
        # An authentification with SCA has at least 2. Most of them seem to have
        # 3 steps with one optional that we skip.

        while token is None and self.login_steps:
            step = self.login_steps[0]
            step_type = step['type']
            step_action = step['action'].lower()
            step_status = step['status'].lower()

            if step_status == 'optional' or step_status == 'done':
                self.login_steps.pop(0)
                continue

            if step_type not in self.known_step_type:
                raise AuthMethodNotImplemented(step_type)

            if step_action == 'init':
                if step_type in ('SCA_PUSH', 'PHONE_OTP'):
                    # Init on known 2fa
                    self.check_interactive()
                    self.send_init_step.go(json={
                        'flow_id': self.login_flow_id,
                        'step_type': step_type,
                        # additionnal_inputs from the context request
                        'additionnal_inputs': self.login_additional_inputs,
                    })
                    self.assert_no_error()
                    new_step_value = self.page.get_step_of(step_type)
                    assert new_step_value['action'].lower() != 'init', 'The action is expected to change.'
                    self.login_steps[0] = new_step_value

                    if step_type == 'PHONE_OTP':
                        extra_data = self.page.get_extra_data()
                        # From translation.json  key: Enter_OTP_Code/Label_Code_Sent
                        label = 'Un nouveau code de sécurité vous a été envoyé par SMS au %s.' % extra_data['masked_phone']
                        raise BrowserQuestion(Value('PHONE_OTP', label=label))
                    elif step_type == 'SCA_PUSH':
                        extra_data = self.page.get_extra_data()
                        raise AppValidation(
                            message=f"Veuillez valider l'opération dans votre application sur {extra_data['device_nickname']}",
                            medium_label=f"{extra_data['device_nickname']}"
                        )
                    raise AssertionError(f'Unexpected behavior while trying to handle the SCA: {step}')
                else:
                    raise AuthMethodNotImplemented(step)

            elif step_action == 'complete':
                if step_type in ('IAD_ACCESS_CODE', 'EMAIL_PASSWORD'):
                    token = self.complete_step(self.password)
                else:
                    # Other type of step should be handled in handle_*
                    raise AssertionError('Unexpected "complete" action for step %s' % step)
            else:
                raise AssertionError('Unkown step action: %s' % step_action)

        if token:
            self.finish_auth_with_token(token)
        else:
            raise BrowserIncorrectPassword()

    def handle_polling(self):
        headers = {'Content-Type': 'application/json'}
        payload = {
            'flow_id': self.login_flow_id,
            'step_type': 'SCA_PUSH',
            'value': '',
        }

        for _ in range(60):
            self.send_complete_step.go(json=payload, headers=headers)
            status = self.page.get_status()
            if not status:
                raise AppValidationExpired(self.page.get_error())

            if status == 'DONE':
                token = self.page.get_token()
                self.update_authorization(self.jwt_token)
                self.execute_login_steps(token)
                return

            # We did not encounter different status that PENDING and DONE, this will let us know if we missed something
            # AppValidationExpired is raised later if token is not found because there's not 'expired' status
            assert status == 'PENDING', f'Unknown polling status {status}'
            time.sleep(10)
        raise AppValidationExpired()

    def complete_step(self, value):
        step = self.login_steps.pop(0)
        step_type = step['type']
        self.send_complete_step.go(json={
            'flow_id': self.login_flow_id,
            'step_type': step_type,
            'value': value,
        })
        self.check_auth_error()
        token = self.page.get_token()
        new_status = self.page.get_step_of(step_type)['status'].lower()

        if token:
            self.new_access_code.go(params={'token': token})
            # For some accounts, the password is temporary and needs to be changed before login
            if 'temporary_access_code' in self.response.json()['body'].values():
                raise ActionNeeded('Vous devez réinitialiser votre mot de passe.')
        else:
            self.logger.warning('ONEY: Token was absent.')

        assert new_status == 'done', 'Status should be done after a complete step'

        return token

    def handle_phone_otp(self):
        token = self.complete_step(self.PHONE_OTP)
        self.execute_login_steps(token)

    def finish_auth_with_token(self, token):
        self.location(
            self.login_success_url,
            params={
                'token': token,
                'customer_session_id': self.login_customer_session_id,
            },
        )

        self.login_steps = None
        self.login_flow_id = None
        self.login_success_url = None
        self.login_customer_session_id = None
        self.login_additional_inputs = None
        self.session.headers.pop('Client-id', None)

        if self.choice.is_here():
            self.has_other = self.has_oney = True
        elif self.dashboard.is_here():
            self.has_other = True
            self.setup_headers_other_space()
        elif self.client.is_here():
            self.has_oney = True
        else:
            parsed_url = urlparse(self.url)
            netloc = parsed_url.netloc
            path = parsed_url.path
            self.logger.info('ONEY SUCCESS REDIRECT URL: %s%s', netloc, path)
            raise BrowserIncorrectPassword()

    def setup_headers_other_space(self):
        assert self.dashboard.is_here()
        try:
            isaac_token = self.page.get_token()
            self.oauth.go(json={
                'header': self.params_headers,
                'isaacToken': isaac_token,
            })
            self.params_headers.update(self.page.get_headers_from_json())
        except (ConnectionError, ReadTimeout):
            raise BrowserUnavailable()

    def setup_headers_login(self):
        try:
            self.jwt_token_page.go(params={
                'localTime': datetime.now().isoformat()[:-3] + 'Z',
            })
            self.jwt_token = self.page.get_token()
            self.update_authorization(self.jwt_token)

        except (ConnectionError, ReadTimeout):
            raise BrowserUnavailable()

    def update_authorization(self, token):
        self.session.headers.update({
            'Authorization': 'Bearer %s' % token,
        })

    def reset_session_for_new_auth(self):
        self.clear_init_cookies()
        self.session.headers.pop('Authorization', None)
        self.session.headers.pop('Origin', None)
        self.params_headers = self.pristine_params_headers.copy()

    def other_space_params_headers(self):
        return {
            'Headers.%s' % key: value
            for key, value in self.params_headers.items()
        }

    def get_referrer(self, oldurl, newurl):
        if newurl.startswith(self.OTHERURL):
            return 'https://espaceclient.oney.fr/'
        else:
            return super(OneyBrowser, self).get_referrer(oldurl, newurl)

    def get_site(self):
        try:
            return self.page.get_site()
        except AttributeError:
            # That error mean that we are on an unknown page or a login page.
            # These case are then handled by try_go_site
            return None

    def try_go_site(self, target_site):
        current_site = self.get_site()
        if current_site == target_site:
            return True

        if target_site == 'oney':
            if not self.has_oney:
                return False

            if not self.choice.is_here():
                self.do_login()
            assert self.choice.is_here()

            self.choice_portal.go(data={'selectedSite': 'ONEY_HISTO'})
        elif target_site == 'other':
            if not self.has_other:
                return False

            if not self.choice.is_here():
                self.do_login()
            assert self.choice.is_here()

            self.choice_portal.go(data={'selectedSite': 'ONEY'})
            self.setup_headers_other_space()
        else:
            raise AssertionError('Unkown target_site: %s' % target_site)

        current_site = self.get_site()
        assert current_site == target_site, (
            'Should be on site %s, landed on %s site instead'
            % (target_site, current_site)
        )
        return True

    def assert_no_error(self):
        error = self.page.get_error()
        # the original error message is :
        # "Authenticator : FM00000001 : Internal error. Please try again after some time or contact administrator. Reason : delivery failed"
        # From the user perspective it only show a generic error message. The error is caused by the SCA system they use
        # that sometime have trouble to communicate with the oney server.
        if error and 'FM00000001 : Internal error' in error:
            raise BrowserUnavailable()
        assert not error, error

    def check_auth_error(self):
        error = self.page.get_error()
        if error:
            incorrect_password_re = (
                # Seen in the following case: the user change its login from a number to its email adress
                r'Le facteur d’authentification est rattaché'
                # Website message: 'Les informations fournies ne nous permettent pas de vous identifier'
                + r"|Le facteur d'authentification n'existe pas"
                + r'|LOGIN_FAILED'
                + r'|L’identité n’existe pas'
            )
            if re.search(incorrect_password_re, error):
                raise BrowserIncorrectPassword()

            browser_unavailable_re = (
                r'Authenticator : Invalid CA response code : 504 Gateway Timeout'
                + r'|.TechnicalError. Read timed out'
            )
            if re.search(browser_unavailable_re, error):
                raise BrowserUnavailable()

            if 'BLOCKED' in error:
                # Website message: 'Pour le débloquer, vous pouvez demander un nouveau mot de passe'
                raise BrowserPasswordExpired()
            if 'NOT_ACTIVATED' in error:
                # An email is sent to the user and needs to be validated
                raise ActionNeeded('Une validation par e-mail est nécessaire pour activer votre compte.')
            raise AssertionError(error)

    @need_login
    def iter_accounts(self):
        accounts = []

        if self.try_go_site('other'):
            self.other_accounts.go(params=self.other_space_params_headers())
            accounts.extend(self.page.iter_accounts())

        if self.try_go_site('oney'):
            if self.client_space.is_here():
                return accounts
            self.client.stay_or_go()
            accounts.extend(self.page.iter_accounts())

        return accounts

    @need_login
    def iter_history(self, account):
        self.try_go_site(account._site)
        if account._site == 'oney':
            if account._num:
                self.card_page.go(acc_num=account._num)
            post = {'task': 'Synthese', 'process': 'SyntheseCompte', 'taskid': 'Releve'}
            self.operations.go(data=post)

            return self.page.iter_transactions(seen=set())

        elif account._site == 'other' and account.type == Account.TYPE_CHECKING:
            try:
                self.other_operations.go(params=self.other_space_params_headers())
            except (ConnectionError, ReadTimeout):
                raise BrowserUnavailable()
            return self.page.iter_history(guid=account._guid, is_coming=False)
        else:
            return []

    @need_login
    def iter_coming(self, account):
        self.try_go_site(account._site)
        if account._site == 'oney':
            if account._num:
                self.card_page.go(acc_num=account._num)
            post = {'task': 'OperationRecente', 'process': 'OperationRecente', 'taskid': 'OperationRecente'}
            self.operations.go(data=post)

            return self.page.iter_transactions(seen=set())

        elif account._site == 'other' and account.type == Account.TYPE_CHECKING:
            try:
                self.other_operations.go(params=self.other_space_params_headers())
            except (ConnectionError, ReadTimeout):
                raise BrowserUnavailable()
            return self.page.iter_history(guid=account._guid, is_coming=True)
        else:
            return []
