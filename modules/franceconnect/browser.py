# Copyright(C) 2012-2020 Powens
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

from urllib.parse import urlparse

from woob.browser import LoginBrowser, URL
from woob.exceptions import BrowserIncorrectPassword, BrowserUserBanned

from .pages import (
    AuthorizePage, AmeliLoginPage, WrongPassAmeliLoginPage, ImpotsLoginAccessPage,
    ImpotsLoginAELPage, ImpotsGetContextPage,
)


class FranceConnectBrowser(LoginBrowser):
    """
    france connect urls work only with nss
    """
    BASEURL = 'https://app.franceconnect.gouv.fr'

    # re set BASEURL to authorize page,
    # because it has to be always same BASEURL, no matter which child module use it with his own BASEURL
    authorize = URL(r'https://app.franceconnect.gouv.fr/api/v1/authorize', AuthorizePage)

    ameli_login_page = URL(r'/FRCO-app/login', AmeliLoginPage)
    ameli_wrong_login_page = URL(r'/FRCO-app/j_spring_security_check', WrongPassAmeliLoginPage)

    impot_login_page = URL(r'https://idp.impots.gouv.fr/LoginAccess', ImpotsLoginAccessPage)
    impot_login_ael = URL(r'https://idp.impots.gouv.fr/LoginAEL', ImpotsLoginAELPage)
    impot_get_context = URL(r'https://idp.impots.gouv.fr/GetContexte', ImpotsGetContextPage)

    def fc_call(self, provider, baseurl):
        self.BASEURL = baseurl
        params = {'provider': provider, 'storeFI': 'false'}
        self.location('/call', params=params)

    def fc_redirect(self, url=None):
        self.BASEURL = 'https://app.franceconnect.gouv.fr'

        if url is not None:
            self.location(url)
        error_message = self.page.get_error_message()
        if error_message:
            if error_message == 'Les identifiants utilisés correspondent à une identité qui ne permet plus la connexion via FranceConnect.':
                raise BrowserUserBanned(error_message)
            raise AssertionError(error_message)
        self.page.redirect()
        parse_result = urlparse(self.url)
        self.BASEURL = parse_result.scheme + '://' + parse_result.netloc

    def login_impots(self, fc_redirection=True):
        """
        Login using the service impots.gouv.fr

        :param fc_redirection: whether or not to redirect to and out of the
        specific service
        """
        if fc_redirection:
            self.fc_call('dgfip', 'https://idp.impots.gouv.fr')

        context_url = self.page.get_url_context()
        url_login_password = self.page.get_url_login_password()

        # POST /GetContexte (ImpotsGetContextPage)
        context_page = self.open(context_url, data={"spi": self.username}).page

        if context_page.has_wrong_login():
            raise BrowserIncorrectPassword(bad_fields=['login'])

        assert context_page.has_next_step(), 'Unexpected behaviour after submitting login for France Connect impôts'

        # POST /LoginAEL (ImpotsLoginAELPage)
        self.page.login(self.username, self.password, url_login_password)

        if self.page.has_wrong_password():
            remaining_attemps = self.page.get_remaining_login_attempts()
            attemps_str = f'{remaining_attemps} essai'
            if int(remaining_attemps) > 1:
                attemps_str = f'{remaining_attemps} essais'
            message = f'Votre mot de passe est incorrect, il vous reste {attemps_str} pour vous identifier.'
            raise BrowserIncorrectPassword(message, bad_fields=['password'])

        assert self.page.is_status_ok(), 'Unexpected behaviour after submitting password for France Connect impôts'

        next_url = self.page.get_next_url()
        self.location(next_url)

        if fc_redirection:
            self.fc_redirect()

    def login_ameli(self, fc_redirection=True):
        """
        Login using the service ameli.fr

        :param fc_redirection: whether or not to redirect to and out of the
        specific service
        """
        if fc_redirection:
            self.fc_call('ameli', 'https://fc.assure.ameli.fr')

        self.page.login(self.username, self.password)
        if self.ameli_wrong_login_page.is_here():
            msg = self.page.get_error_message()
            if msg:
                raise BrowserIncorrectPassword(msg)
            raise AssertionError('Unexpected behaviour at login')

        if fc_redirection:
            self.fc_redirect()
