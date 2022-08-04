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
    DocumentsSignaturePage, RedirectToUserAgreementPage, UserAgreementPage, UserInfosPage,
)


class GmfBrowser(LoginBrowser):
    BASEURL = 'https://mon-espace-societaire.gmf.fr'

    login = URL(r'https://espace-assure.gmf.fr/public/pages/securite/IC2.faces', LoginPage)
    home = URL(r'https://espace-assure.gmf.fr/auth_soc_jwt', HomePage)
    user_infos = URL(r'/cap-mx-espacesocietaire-internet/api/users/infos', UserInfosPage)
    redirect_to_user_agreement = URL('^$', RedirectToUserAgreementPage)
    user_agreement = URL(r'/restreint/pages/securite/IC9.faces', UserAgreementPage)
    accounts = URL(r'/cap-mx-espacesocietaire-internet/api/prestation', AccountsPage)
    transactions_investments = URL(
        r'https://espace-assure.gmf.fr/pointentree/contratvie/detailsContrats',
        TransactionsInvestmentsPage
    )
    all_transactions = URL(r'/pages/contratvie/detailscontrats/.*\.faces', AllTransactionsPage)
    documents_signature = URL(r'/public/pages/authentification/.*\.faces', DocumentsSignaturePage)

    def do_login(self):
        self.login.go()
        self.page.login(self.username, self.password)
        if self.login.is_here():
            raise BrowserIncorrectPassword(self.page.get_error())

        # csrf token is needed for accounts page
        self.user_infos.go()
        self.session.headers['covea-csrf-token'] = self.page.get_csrf_token()

    @need_login
    def iter_accounts(self):
        self.accounts.go()
        return self.page.iter_accounts()

    @need_login
    def iter_history(self, account):
        self.accounts.stay_or_go()
        data = self.page.get_details_page_form_data(account)
        self.transactions_investments.go(data=data)
        self.page.show_all_transactions()
        return self.page.iter_history()

    @need_login
    def iter_investment(self, account):
        self.accounts.stay_or_go()
        data = self.page.get_details_page_form_data(account)
        self.transactions_investments.go(data=data)
        if self.page.has_investments():
            return self.page.iter_investments()
        return []
