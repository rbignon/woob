# Copyright(C) 2016      Edouard Lambert
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

from woob.browser import URL
from woob.tools.url import get_url_param
from woob_modules.erehsbc.browser import ErehsbcBrowser
from woob_modules.erehsbc.pages import AuthenticationPage as ErehsbcAuthenticationPage


class EsaliaBrowser(ErehsbcBrowser):
    BASEURL = 'https://salaries.esalia.com'
    SLUG = 'sg'
    LANG = 'fr'  # ['fr', 'en']

    login_page = URL(r'/portal/salarie-(?P<slug>\w+)/connect')
    authentication_page = URL(
        r'https://iam.esalia.com/connect/json/realms/root/realms/sg_ws/authenticate',
        ErehsbcAuthenticationPage
    )

    def build_authentication_params(self):
        # Keeping redirect_uri in the state for OTP connections
        # that will need it in finalize_login
        self.redirect_uri = get_url_param(self.url, 'goto')
        return {
            'locale': 'fr',
            'goto': self.redirect_uri,
            'authIndexType': 'service',
            'authIndexValue': 'authn_sg_ws',
        }
