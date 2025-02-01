# Copyright(C) 2019      Vincent A
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

from .pages import AccountsPage, AfterLoginPage, LoginPage, TaxDocsPage


class PrimonialreimBrowser(LoginBrowser):
    BASEURL = "https://www.primonialreim.fr"

    login = URL("/fr/login", LoginPage)
    accounts = URL("/group/extranet-associes/mon-patrimoine", AccountsPage)
    tax_documents = URL("/group/extranet-associes/ma-fiscalit%C3%A9", TaxDocsPage)
    home = URL("/group/extranet-associes", AfterLoginPage)

    def do_login(self):
        self.login.go()
        self.page.do_login(self.username, self.password)
        # twice because site submits username first then password
        self.page.do_login(self.username, self.password)

    @need_login
    def iter_accounts(self):
        self.accounts.go()
        return self.page.iter_accounts()

    @need_login
    def iter_documents(self):
        self.tax_documents.go()
        return self.page.iter_documents()
