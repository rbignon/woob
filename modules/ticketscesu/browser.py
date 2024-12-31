# -*- coding: utf-8 -*-

# Copyright(C) 2019      Antoine BOSSY
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
from woob.exceptions import ActionNeeded, ActionType, BrowserIncorrectPassword

from .pages import AccountsPage, LoginPage, ProfilePage


class TicketCesuBrowser(LoginBrowser):
    BASEURL = 'https://ebeneficiaire.cesu-as.fr'

    login_page = URL('/login.aspx', LoginPage)
    profile_page = URL('/customerManagement/ProfileManagement.aspx', ProfilePage)
    accounts_page = URL('/PaymentManagement/PaymentAccountInfoFullDemat.aspx', AccountsPage)


    def do_login(self):
        self.login_page.go()
        self.page.login(self.username, self.password)

        if self.login_page.is_here():
            # Wrong credentials leads back here, with JS generated message, hard-coded in the exception raised.
            raise BrowserIncorrectPassword('login et / ou mot de passe erroné')


        elif self.profile_page.is_here():
            raise ActionNeeded(
                locale="en-US", message="Please agree CGU on the CESU website.",
                action_type=ActionType.ACKNOWLEDGE,
            )

    @need_login
    def iter_accounts(self):
        self.accounts_page.go()
        return self.page.iter_accounts()

    @need_login
    def iter_history(self, account):
        self.accounts_page.stay_or_go()
        self.page.go_to_transactions_page(account._page)
        return self.page.iter_transactions()

    @need_login
    def iter_subscription(self):
        return []
