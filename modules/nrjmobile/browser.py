# Copyright(C) 2022-2023 Powens
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

from woob.browser.browsers import LoginBrowser, StatesMixin, need_login
from woob.browser.url import URL
from woob.exceptions import (
    BrowserIncorrectPassword, BrowserUnavailable, RecaptchaV2Question,
)

from .pages import (
    HomePage, LoginPage, OrderBillsPage, PeriodicBillsPage,
    ProfilePage, SubscriptionPage,
)


class NRJMobileBrowser(LoginBrowser, StatesMixin):
    BASEURL = 'https://www.nrjmobile.fr/fr/'

    login_page = URL(r'identification/authentification.html', LoginPage)
    home_page = URL(r'client/index.html', HomePage)
    profile_page = URL(
        r'client/InfoPerso/CoordonneesTitulaire/Default.html',
        ProfilePage,
    )
    subscription_page = URL(r'client/HubForfait.html', SubscriptionPage)
    order_bills_page = URL(
        r'client/Mobile/FactureAchat/Default.html',
        OrderBillsPage,
    )
    periodic_bills_page = URL(
        r'client/Consommations/Factures/Default.html',
        PeriodicBillsPage,
    )

    def __init__(self, config, *args, **kwargs):
        super().__init__(
            config['login'].get(),
            config['password'].get(),
            *args, **kwargs,
        )

        self.config = config

    def do_login(self):
        self.login_page.stay_or_go()

        captcha_response = self.config['captcha_response'].get()
        if not captcha_response:
            raise RecaptchaV2Question(
                website_key=self.page.get_site_key(),
                website_url=self.url,
            )

        self.page.do_login(self.username, self.password, captcha_response)
        if self.login_page.is_here():
            message = self.page.get_error_message()
            raise BrowserIncorrectPassword(message)

    @need_login
    def get_subscription(self):
        self.subscription_page.go()

        message = self.page.get_error_message()
        if message:
            if 'Problème technique' in message:
                raise BrowserUnavailable(message)

            raise AssertionError(f'Unknown error message: {message!r}')

        return self.page.get_subscription()

    @need_login
    def iter_documents(self):
        self.periodic_bills_page.stay_or_go()
        for bill in self.page.iter_documents():
            yield bill

        self.order_bills_page.go()
        for bill in self.page.iter_documents():
            yield bill

    @need_login
    def download_document(self, document):
        if document._from == 'periodic':
            self.periodic_bills_page.stay_or_go()
        elif document._from == 'orders':
            self.order_bills_page.stay_or_go()
        else:
            raise AssertionError('Unknown document source %r' % document._from)

        return self.page.download_document(document.id)

    @need_login
    def get_profile(self):
        self.profile_page.go()
        return self.page.get_profile()
