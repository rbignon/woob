# -*- coding: utf-8 -*-

# Copyright(C) 2017      Tony Malto
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

from woob.browser import LoginBrowser, URL, need_login
from woob.exceptions import BrowserIncorrectPassword

from .pages import (
    LoginPage, HomePage, AccountsPage, TransactionsInvestmentsPage, AllTransactionsPage,
    DocumentsSignaturePage, RedirectToUserAgreementPage, UserAgreementPage,
)


class GmfBrowser(LoginBrowser):
    BASEURL = 'https://espace-assure.gmf.fr'

    login = URL(r'/public/pages/securite/IC2.faces', LoginPage)
    home = URL(r'/auth_soc_jwt', HomePage)
    redirect_to_user_agreement = URL('^$', RedirectToUserAgreementPage)
    user_agreement = URL(r'restreint/pages/securite/IC9.faces', UserAgreementPage)
    accounts = URL(r'/pointentree/client/homepage', AccountsPage)
    transactions_investments = URL(r'/pointentree/contratvie/detailsContrats', TransactionsInvestmentsPage)
    all_transactions = URL(r'/pages/contratvie/detailscontrats/.*\.faces', AllTransactionsPage)
    documents_signature = URL(r'/public/pages/authentification/.*\.faces', DocumentsSignaturePage)

    def do_login(self):
        self.login.go().login(self.username, self.password)
        if self.login.is_here():
            raise BrowserIncorrectPassword(self.page.get_error())

    @need_login
    def iter_accounts(self):
        for account in self.page.iter_accounts():
            self.accounts.go()
            self.page.go_details_page(account)
            account.opening_date = self.page.get_opening_date()
            yield account

    @need_login
    def iter_history(self, account):
        self.go_details_page(account)
        self.page.show_all_transactions()
        return self.page.iter_history()

    @need_login
    def iter_investment(self, account):
        self.go_details_page(account)
        assert self.transactions_investments.is_here()
        if self.page.has_investments():
            return self.page.iter_investments()
        return []
