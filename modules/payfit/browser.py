# -*- coding: utf-8 -*-

# Copyright(C) 2021      Florent Fourcot
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

from woob.browser import LoginBrowser, need_login, URL
from woob.browser.exceptions import ClientError
from woob.browser.profiles import Firefox
from woob.exceptions import BrowserIncorrectPassword
from woob.capabilities.base import find_object
from woob.capabilities.bill import DocumentNotFound
from .pages import LoginPage, AccountListPage, UserInfoPage, DocumentsPage, CategoryPage


class PayFitBrowser(LoginBrowser):
    BASEURL = 'https://api.payfit.com/'
    PROFILE = Firefox()

    login = URL('/auth/signin', LoginPage)
    account_list = URL('/hr/individuals/accounts/list', AccountListPage)  # GET
    user_info = URL('/hr/user/info', UserInfoPage)  # POST
    set_account = URL('/auth/updateCurrentAccount')
    document_list = URL('/files/files', DocumentsPage)
    category_info = URL('/files/category', CategoryPage)
    download = URL(r'/files/file/(?P<id>\w+)\?attachment=1')

    def do_login(self):
        data = {"email": self.username,
                "password": self.password,
                "remember": False}
        try:
            self.login.go(json=data)
        except ClientError:
            raise BrowserIncorrectPassword()

    @need_login
    def iter_documents(self, subscription):
        employee_id, company_id = subscription.id.split("-")
        self.set_account.go(params={"companyId": company_id, "employeeId": employee_id})
        self.category_info.go(params={"name": "payslip", "country": subscription._country})
        payslip_id = self.page.get_id()
        self.document_list.go(json={"employeeIds": [employee_id],
                                    "companyIds": [company_id],
                                    "categoryIds": [payslip_id]})
        yield from self.page.iter_documents()

    @need_login
    def iter_subscription(self):
        self.account_list.go()
        for company, employee in self.page.iter_accounts():
            self.set_account.go(params={"companyId": company["id"], "employeeId": employee["id"]})
            self.user_info.go(data={})
            yield from self.page.get_subscription(company, employee)

    @need_login
    def get_document(self, id):
        return find_object(self.iter_documents(None), id=id,
                           error=DocumentNotFound)
