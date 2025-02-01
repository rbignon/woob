# Copyright(C) 2016      Edouard Lambert
# Copyright(C) 2016-2022 Powens
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

from woob.browser import URL, LoginBrowser, need_login
from woob.capabilities.captcha import RecaptchaV2Question
from woob.exceptions import BrowserIncorrectPassword

from .pages import CaptchaPage, DocumentsDetailsPage, DocumentsPage, LoginPage, PeriodPage, ProfilePage


class MaterielnetBrowser(LoginBrowser):
    BASEURL = "https://secure.materiel.net"

    login = URL(r"/Login/Login", LoginPage)
    captcha = URL(r"/pm/client/captcha.html", CaptchaPage)
    profile = URL(r"/Identity", ProfilePage)
    documents = URL(r"/Orders/PartialCompletedOrdersHeader", DocumentsPage)
    document_details = URL(r"/Orders/PartialCompletedOrderContent", DocumentsDetailsPage)
    periods = URL(r"/Orders/CompletedOrdersPeriodSelection", PeriodPage)

    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config

    def do_login(self):
        self.login.go()
        sitekey = self.page.get_recaptcha_sitekey()
        # captcha is not always present
        if sitekey:
            if not self.config["captcha_response"].get():
                raise RecaptchaV2Question(website_key=sitekey, website_url=self.url)

        self.page.login(self.username, self.password, self.config["captcha_response"].get())

        if self.captcha.is_here():
            BrowserIncorrectPassword()

        if self.login.is_here():
            error = self.page.get_error()
            # when everything is good we land on this page
            if error:
                raise BrowserIncorrectPassword(error)

    @need_login
    def get_subscription_list(self):
        # There is no subscription. The profile page is used to generate one
        # so only one subscription will be returned.
        return self.profile.go().get_subscriptions()

    @need_login
    def iter_documents(self):
        periods = self.periods.go(method="POST").get_periods()

        # data will be a dict containing information to retrieve bills by period
        for period in periods:
            yield from self.documents.go(data=period).get_documents()
