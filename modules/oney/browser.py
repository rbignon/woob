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

from __future__ import unicode_literals

from datetime import datetime

from woob.tools.compat import urlparse
from woob.capabilities.bank import Account
from woob.exceptions import BrowserIncorrectPassword, BrowserPasswordExpired
from woob.browser import LoginBrowser, URL, need_login

from .pages import (
    LoginPage, ClientPage, OperationsPage, ChoicePage,
    ContextInitPage, SendUsernamePage, SendPasswordPage, CheckTokenPage, ClientSpacePage,
    OtherDashboardPage, OAuthPage, AccountsPage, JWTTokenPage, OtherOperationsPage,
)

__all__ = ['OneyBrowser']


class OneyBrowser(LoginBrowser):
    BASEURL = 'https://www.oney.fr'
    LOGINURL = 'https://login.oney.fr'
    OTHERURL = 'https://middle.mobile.oney.io'

    home_login = URL(
        r'/site/s/login/login.html',
        LoginPage
    )
    login = URL(
        r'https://login.oney.fr/login',
        r'https://login.oney.fr/context',
        LoginPage
    )

    send_username = URL(LOGINURL + r'/middle/authenticationflowinit', SendUsernamePage)
    send_password = URL(LOGINURL + r'/middle/completeauthflowstep', SendPasswordPage)
    context_init = URL(LOGINURL + r'/middle/context', ContextInitPage)

    check_token = URL(LOGINURL + r'/middle/check_token', CheckTokenPage)

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
    jwt_token = URL(OTHERURL + r'/JWTToken', JWTTokenPage)
    oauth = URL(OTHERURL + r'/web/login/oauth', OAuthPage)
    other_accounts = URL(OTHERURL + r'/web/dashboard', AccountsPage)
    other_operations = URL(OTHERURL + r'/web/operation/operations', OtherOperationsPage)

    has_oney = False
    has_other = False
    card_name = None
    is_mail = False
    pristine_params_headers = {
        'Environment': "PRD",
        'Origin': "Web",
        'IsLoggedIn': False,
    }
    params_headers = pristine_params_headers.copy()

    def do_login(self):
        self.reset_session_for_new_auth()

        self.home_login.go(method="POST")
        context_token = self.page.get_context_token()
        assert context_token is not None, "Should not have context_token=None"

        self.context_init.go(params={'contextToken': context_token})
        success_url = self.page.get_success_url()
        customer_session_id = self.page.get_customer_session_id()

        self.session.headers.update({'Client-id': self.page.get_client_id()})

        # There is a VK on the website but it does not encode the password
        self.login.go()
        if '@' in self.username:
            auth_type = 'EML'
            step_type = 'EMAIL_PASSWORD'
            self.is_mail = True
        else:
            auth_type = 'IAD'
            step_type = 'IAD_ACCESS_CODE'

        self.send_username.go(json={
            'authentication_type': 'LIGHT',
            'authentication_factor': {
                'public_value': self.username,
                'type': auth_type,
            }
        })

        flow_id = self.page.get_flow_id()

        self.send_password.go(json={
            'flow_id': flow_id,
            'step_type': step_type,
            'value': self.password,
        })

        error = self.page.get_error()
        if error:
            if error == 'Authenticator : Le facteur d’authentification est rattaché':
                raise BrowserPasswordExpired()
            raise BrowserIncorrectPassword(error)

        token = self.page.get_token()

        self.check_token.go(params={'token': token})
        self.location(success_url, params={
            'token': token,
            'customer_session_id': customer_session_id,
        })

        if self.choice.is_here():
            self.other_space_url = self.page.get_redirect_other_space()
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
            self.logger.info("ONEY SUCCESS REDIRECT URL: %s%s", netloc, path)
            raise BrowserIncorrectPassword()

    def setup_headers_other_space(self):
        assert self.dashboard.is_here()
        isaac_token = self.page.get_token()

        self.session.headers.update({
            'Origin': "https://espaceclient.oney.fr",
        })
        self.jwt_token.go(params={
            'localTime': datetime.now().isoformat()[:-3]+ 'Z'
        })
        self.update_authorization(self.page.get_token())

        self.oauth.go(json={
            'header': self.params_headers,
            'isaacToken': isaac_token,
        })

        self.params_headers.update(self.page.get_headers_from_json())

    def update_authorization(self, token):
        self.session.headers.update({
            'Authorization': 'Bearer %s' % token
        })

    def reset_session_for_new_auth(self):
        self.session.cookies.clear()
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
            return "https://espaceclient.oney.fr/"
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

            # if no redirect was found in the choice_page we try the previous method. Due to a lack of example
            # it might be deprecated
            if self.other_space_url:
                self.location(self.other_space_url)
                self.client_space.go()
            else:
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
        assert current_site == target_site, 'Should be on site %s, landed on %s site instead' % (target_site, current_site)
        return True

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
            self.other_operations.go(params=self.other_space_params_headers())
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
            self.other_operations.go(params=self.other_space_params_headers())
            return self.page.iter_history(guid=account._guid, is_coming=True)
        else:
            return []
