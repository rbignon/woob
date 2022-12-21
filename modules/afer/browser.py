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

from __future__ import unicode_literals


from woob.browser import AbstractBrowser
from woob.browser.exceptions import ClientError


class AferBrowser(AbstractBrowser):
    PARENT = 'aviva'
    PARENT_ATTR = 'package.browser.AvivaBrowser'
    BASEURL = 'https://adherent.gie-afer.fr'

    def __init__(self, *args, **kwargs):
        super(AferBrowser, self).__init__(*args, **kwargs)
        self.subsite = 'espaceadherent'

    def post_login_credentials(self):
        """
        Overriding method from parent to bypass cloudflare for afer.

        When posting the credentials, we get a 302 into 403 cloudflare.
        To bypass 403 we can catch it and retry initial 302 url location.
        The other part of the process does not change.
        """
        try:
            self.page.login(self.username, self.password)
        except ClientError as e:
            if (
                e.response.status_code == 403
                and 'cloudflare' in e.response.text
            ):
                self.logger.debug('login blocks by cloudflare. Force redirection to bypass it...')
                self.location(e.response.url)
            else:
                raise
