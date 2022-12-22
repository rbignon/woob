# -*- coding: utf-8 -*-

# Copyright(C) 2012-2019  Budget Insight
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


from urllib.parse import urlparse

from woob.browser import AbstractBrowser
from woob.browser.exceptions import BrowserTooManyRequests, ClientError
from woob.exceptions import BrowserUnavailable


class AferBrowser(AbstractBrowser):
    PARENT = 'aviva'
    PARENT_ATTR = 'package.browser.AvivaBrowser'
    BASEURL = 'https://adherent.gie-afer.fr'

    def __init__(self, *args, **kwargs):
        super(AferBrowser, self).__init__(*args, **kwargs)
        self.subsite = 'espaceadherent'

    def post_login_credentials(self):
        """
        Overriding method from parent to bypass cloudflare.

        When posting the credentials, we get multiple 302/301 into 403 cloudflare.
        The first redirection leads to the right page but in http.
        This results in a new redirect with the correct scheme but triggering CloudFlare protection.
        To solve this we must not follow the redirects
        and go directly to the right page after changing the scheme.
        The other part of the login process does not change.
        """
        self.page.login(self.username, self.password, False)

        for _ in range(5):
            # Loop to handle possible redirects to actionneeded
            # range(5) to avoid infiny 302 loop
            if self.response.status_code != 302:
                break

            redirect_url = self.response.headers.get('location')
            redirect_url = urlparse(redirect_url)._replace(scheme='https').geturl()
            try:
                self.location(redirect_url, allow_redirects=False)
            except ClientError as e:
                if e.response.status_code == 429:
                    raise BrowserTooManyRequests()
                raise
        else:
            # Too many unexpected redirections
            raise BrowserUnavailable()
