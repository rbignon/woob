# -*- coding: utf-8 -*-

# Copyright(C) 2012-2021  Budget Insight
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


from weboob.browser import LoginBrowser, need_login, URL
from weboob.exceptions import BrowserIncorrectPassword

from .pages import LoginPage, MultiPage, HistoryPage


class TransatplanBrowser(LoginBrowser):
    BASEURL = 'https://transatplan.cic.fr'

    login = URL(r'/fr/index.html', '/fr/identification/default.cgi', LoginPage)
    history = URL(r'/fr/client/votre-situation.aspx\?.*', HistoryPage)
    multi = URL(r'/fr/client/votre-situation.aspx\?FID=GoSituation',
                r'/fr/client/votre-situation.aspx\?.*',
                MultiPage)

    def do_login(self):
        self.login.go()
        self.page.login(self.username, self.password)
        if self.login.is_here():
            raise BrowserIncorrectPassword(self.page.get_error())
        assert self.page

    @need_login
    def iter_accounts(self):
        self.multi.go()
        for url, label in self.page.iter_contracts():
            self.location(url)
            assert self.multi.is_here()
            self.page.go_accounts()

            for account in self.page.iter_especes():
                account._contract = url
                yield account

            for account in self.page.iter_titres():
                account._contract = url
                yield account

    @need_login
    def iter_history(self, account):
        if not account.url:
            raise NotImplementedError()

        self.location(account.url)
        return self.page.iter_history()

    @need_login
    def iter_investment(self, account):
        self.location(account._contract)
        self.page.go_accounts()
        for inv in self.page.iter_investment():
            if inv.code == account.id:
                return [inv]
        return []
