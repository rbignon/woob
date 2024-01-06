# Copyright(C) 2024      Ludovic LANGE
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

import random
from base64 import b64encode
from hashlib import sha256

from woob.browser import URL
from woob_modules.cmso.par.browser import CmsoParBrowser


__all__ = ['CCFParBrowser', 'CCFProBrowser']

class CCFBrowser(CmsoParBrowser):
    arkea = 'MG'  # Needed for the X-ARKEA-EFS header
    arkea_si = None
    AUTH_CLIENT_ID = "S4dgkKwTA7FQzWxGRHPXe6xNvihEATOY"

    def __init__(self, *args, **kwargs):
        # most of url return 403 without this origin header
        kwargs['origin'] = self.original_site
        super().__init__(*args, **kwargs)

    def code_challenge(self):
        """Generate a code challenge needed to go through the authorize end point
        and get a session id.
        Found in domi-auth-fat.js (45394)"""

        base = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        code_challenge = ''.join(random.choices(base, k=39))
        return code_challenge

    def auth_state(self):
        """Generate a state needed to go through the authorize end point
        and get a session id.
        Found in domi-auth-fat.js (49981)"""

        base = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        state = 'auth_' + ''.join(random.choices(base, k=25))

        return state

    def code_verifier(self, code_challenge):
        """Generate a code verifier that will have to match the sha256 of the code_challenge
        on the server side.
        Found in domi-auth-fat.js (49986)"""

        digest = sha256(code_challenge.encode('utf-8')).digest()
        code_verifier = b64encode(digest)

        return code_verifier.decode()

    def get_pkce_codes(self):
        """Override parent (cf Axa).

        Returns code_verifier (/oauth/token), code_challenge (build_authorization_uri_params() / /oauth/authorize)
        """
        code_challenge = self.code_challenge()
        return self.code_verifier(code_challenge), code_challenge

    def build_authorization_uri_params(self):
        params = super().build_authorization_uri_params()
        params['state'] = self.auth_state()
        return params

    def build_request(self, *args, **kwargs):
        headers = kwargs.setdefault('headers', {})
        headers['x-apikey'] = self.arkea_client_id
        return super().build_request(*args, **kwargs)


class CCFParBrowser(CCFBrowser):
    BASEURL = 'https://api.ccf.fr'
    original_site = 'https://mabanque.ccf.fr'
    SPACE = "PART"
    arkea_client_id = "JcqCF4MXkladWOKb4hRJGw7xEEuCFyXu"
    redirect_uri = '%s/auth/checkuser' % original_site
    error_uri = '%s/auth/errorauthn' % original_site


class CCFProBrowser(CCFBrowser):
    BASEURL = 'https://api.cmb.fr'
    original_site = 'https://pro.ccf.fr'
    SPACE = "PRO"
    arkea_client_id = "029Ao3yX6YRqbz9DtlSiIrFvgwuMBv9l"
    redirect_uri = '%s/auth/checkuser' % original_site
    error_uri = '%s/auth/errorauthn' % original_site
