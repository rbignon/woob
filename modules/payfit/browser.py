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

import hashlib
import hmac

from woob.browser import URL, LoginBrowser, need_login
from woob.browser.exceptions import ClientError
from woob.exceptions import BrowserIncorrectPassword

from .pages import CategoryPage, DocumentsPage, UserAccountsPage, UserInfoPage


class PayFitBrowser(LoginBrowser):
    BASEURL = 'https://api.payfit.com/'

    login = URL('/auth/signin')
    user_accounts = URL('/auth/accounts', UserAccountsPage)
    user_info = URL('/hr/user/info', UserInfoPage)
    update_current_account = URL('/auth/updateCurrentAccount')
    category_info = URL('/files/category', CategoryPage)
    documents = URL('/files/files', DocumentsPage)
    download = URL(r'/files/file/(?P<id>\w+)\?attachment=1')

    def do_login(self):
        mac = hmac.new(self.password.encode(), msg=b'', digestmod=hashlib.sha256)
        password = mac.hexdigest()

        data = {
            'email': self.username,
            'password': password,
            'remember': False,
        }

        try:
            self.login.go(json=data)
        except ClientError as e:
            if e.response.status_code == 400:
                json_response = e.response.json()
                error_message = json_response.get('error', '')
                if 'password_or_email' in error_message:
                    raise BrowserIncorrectPassword(error_message)
                raise AssertionError(f'unhandled error at login: {error_message}')
            raise

    @need_login
    def iter_subscription(self):
        self.user_accounts.go()

        for company_id, employee_id in self.page.iter_company_and_employee_ids():
            params = {
                'companyId': company_id,
                'employeeId': employee_id,
            }
            # CAUTION: stateful website, we have to select the current account
            self.update_current_account.go(params=params)
            self.user_info.go(method='POST')
            yield self.page.get_subscription(company_id=company_id, employee_id=employee_id)

    @need_login
    def iter_documents(self, subscription):
        params = {
            'companyId': subscription._company_id,
            'employeeId': subscription._employee_id,
        }
        # select the current account to get its documents
        self.update_current_account.go(params=params)

        params = {
            'name': 'payslip',  # get a 400 response code without this
            'country': subscription._country,  # get an empty response when call documents URL without this
        }
        self.category_info.go(params=params)
        category_id = self.page.get_category_id()

        data = {
            'employeeIds': [subscription._employee_id],
            'companyIds': [subscription._company_id],
            'categoryIds': [category_id],
        }
        self.documents.go(json=data)
        return self.page.iter_documents()
