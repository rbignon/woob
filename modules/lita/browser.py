# -*- coding: utf-8 -*-

# Copyright(C) 2021      Damien Ramelet
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
from woob.exceptions import BrowserIncorrectPassword

from .pages import DashboardPage, InvestmentsDetailsPage, InvestmentsListPage, LoginPage, ProfilePage


class LitaBrowser(LoginBrowser):
    BASEURL = "https://fr.lita.co"

    login = URL(r"/users/sign_in", LoginPage)
    dashboard = URL(r"/investors/dashboard", DashboardPage)
    profile = URL(r"/investors/identity/edit", ProfilePage)
    investments_list = URL(r"/investors/subscriptions$", InvestmentsListPage)
    investments_details = URL(r"investors/subscriptions/(?P<id>\d+)/shares", InvestmentsDetailsPage)

    def do_login(self):
        self.login.go()
        self.page.do_login(username=self.username, password=self.password)
        # If login is successful, we should be redirected to the home page
        if self.login.is_here():
            raise BrowserIncorrectPassword(self.page.get_error_msg())

    @need_login
    def get_user_account(self):
        self.dashboard.go()
        return self.page.get_account()

    @need_login
    def iter_investments(self):
        self.investments_list.go()
        for _id, label in self.page.iter_investments():
            self.investments_details.go(id=_id)
            invest = self.page.get_investments_details()
            invest.label = label
            yield invest

    @need_login
    def get_profile(self):
        self.profile.go()
        return self.page.get_profile()
