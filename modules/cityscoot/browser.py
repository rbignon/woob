# Copyright(C) 2017      P4ncake
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


from woob.browser import URL, LoginBrowser, need_login
from woob.capabilities.captcha import RecaptchaV2Question
from woob.exceptions import BrowserIncorrectPassword

from .pages import DocumentsPage, LoginPage, OtpPage, SubscriptionsPage


class CityscootBrowser(LoginBrowser):
    BASEURL = 'https://moncompte.cityscoot.eu'

    otp = URL(r'/$', OtpPage)
    login = URL(r'/$', LoginPage)
    subscriptions = URL(r'/users$', SubscriptionsPage)
    documents = URL(r'/factures/view$', DocumentsPage)

    def __init__(self, config, *args, **kwargs):
        self.config = config
        kwargs['username'] = self.config['login'].get()
        kwargs['password'] = self.config['password'].get()
        super().__init__(*args, **kwargs)

        self.subs = None
        self.docs = {}

    def do_login(self):
        self.login.go()
        if self.page.has_captcha() and self.config['captcha_response'].get() is None:
            website_key = self.page.get_captcha_key()
            raise RecaptchaV2Question(website_key=website_key, website_url=self.url)

        self.page.login(self.username, self.password, self.config['captcha_response'].get())

        if self.otp.is_here():
            # yes we can avoid the otp ... wtf
            self.subscriptions.go()
            assert self.subscriptions.is_here(), "we must handle the otp"

        if self.login.is_here():
            msg = self.page.get_error_login()
            if msg:
                if 'Email ou mot de passe incorrect' in msg:
                    raise BrowserIncorrectPassword(msg)
            raise Exception("Unhandled error at login: {}".format(msg or ""))

    @need_login
    def get_subscription_list(self):
        if self.subs is None:
            self.subs = [self.subscriptions.stay_or_go().get_item()]
        return self.subs

    @need_login
    def iter_documents(self, subscription):
        if subscription.id not in self.docs:
            self.docs[subscription.id] = [d for d in self.documents.stay_or_go().iter_documents(subid=subscription.id)]
        return self.docs[subscription.id]
