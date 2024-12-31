# -*- coding: utf-8 -*-

# Copyright(C) 2015      Romain Bignon
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

from urllib.parse import urljoin

from woob.browser import URL, LoginBrowser, need_login

from .pages import AccountsPage, HistoryPage, LoginConfirmPage, LoginPage, RibPage, RibPDFPage


class ThemisBrowser(LoginBrowser):
    BASEURL = 'https://esab.themisbanque.eu/'

    TIMEOUT = 400

    home = URL(r'/es@b/fr/esab.jsp')
    login = URL(r'/es@b/fr/codeident.jsp', LoginPage)
    login_confirm = URL(r'/es@b/servlet/internet0.ressourceWeb.servlet.Login', LoginConfirmPage)
    accounts = URL(r'/es@b/servlet/internet0.ressourceWeb.servlet.PremierePageServlet\?pageToTreatError=fr/Infos.jsp&dummyDate=',
                r'/es@b/servlet/internet0.ressourceWeb.servlet.PremierePageServlet\?cryptpara=.*',
                r'/es@b/servlet/internet0.ressourceWeb.servlet.EsabServlet.*',
                AccountsPage)
    history = URL(r'/es@b/servlet/internet0.ressourceWeb.servlet.ListeDesMouvementsServlet.*', HistoryPage)
    rib = URL(r'/es@b/fr/rib.jsp\?cryptpara=.*', RibPage)
    rib_pdf = URL(r'/es@b/servlet/internet0.ressourceWeb.servlet.RibPdfDownloadServlet', RibPDFPage)

    def do_login(self):
        self.home.go()
        self.login.go()
        self.page.login(self.username, self.password)

    @need_login
    def iter_accounts(self):
        self.accounts.stay_or_go()
        # sometimes when the user has messages, accounts's page will redirect
        # to the message page and the user will have to click "ok" to access his accounts
        # this will happen as long as the messages aren't deleted.
        # In this case, accounts may be reached through a different link (in the "ok" button)
        acc_link = self.page.get_acc_link()
        if acc_link:
            self.location(urljoin(self.BASEURL, acc_link))
        return self.page.iter_accounts()

    @need_login
    def get_history(self, account):
        if account._link:
            self.location(account._link)
            for tr in self.page.get_operations():
                yield tr

    @need_login
    def get_profile(self):
        accounts = list(self.iter_accounts())
        self.location(accounts[0]._url)
        return self.page.get_profile()
