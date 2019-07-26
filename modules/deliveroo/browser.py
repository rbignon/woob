# -*- coding: utf-8 -*-

# Copyright(C) 2012-2022  Budget Insight
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


from weboob.browser import LoginBrowser, URL, need_login
from weboob.exceptions import BrowserIncorrectPassword, NocaptchaQuestion
from weboob.browser.exceptions import ClientError

from .pages import LoginPage, ProfilePage, DocumentsPage, HomePage


class DeliverooBrowser(LoginBrowser):
    BASEURL = 'https://deliveroo.fr'

    home = URL(r'/fr/$', HomePage)
    login = URL(r'/fr/login', LoginPage)
    profile = URL(r'/fr/account$', ProfilePage)
    documents = URL(r'https://consumer-ow-api.deliveroo.com/orderapp/v1/users/(?P<subid>.*)/orders', DocumentsPage)

    def __init__(self, config, *args, **kwargs):
        super(DeliverooBrowser, self).__init__(*args, **kwargs)
        self.config = config

    def go_login(self):
        try:
            self.login.go()
        except ClientError as error:
            if error.response.status_code != 403:
                raise

            self.page = HomePage(self, error.response)

    def do_login(self):
        self.go_login()
        if self.config['captcha_response'].get():
            self.page.submit_form(self.config['captcha_response'].get())
        elif self.home.is_here():
            site_key = self.page.get_recaptcha_site_key()
            raise NocaptchaQuestion(website_key=site_key, website_url=self.page.url)

        self.session.headers.update({'x-csrf-token': self.page.get_csrf_token()})
        try:
            self.location('/fr/auth/login', json={'email': self.username, 'password': self.password})
        except ClientError as exc:
            raise BrowserIncorrectPassword(str(exc))

    @need_login
    def get_subscription_list(self):
        self.profile.stay_or_go()
        assert self.profile.is_here()
        yield self.page.get_item()

    @need_login
    def iter_documents(self, subscription):
        headers = {'authorization': 'Bearer %s' % self.session.cookies['consumer_auth_token']}
        self.documents.go(subid=subscription.id, params={'limit': 25, 'offset': 0}, headers=headers)
        assert self.documents.is_here()

        return self.page.get_documents(subid=subscription.id, baseurl=self.BASEURL)
