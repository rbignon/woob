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


from woob.browser.pages import LoggedPage, JsonPage
from woob.browser.elements import ItemElement, DictElement, method
from woob.browser.filters.json import Dict
from woob.capabilities.bill import Subscription, Document
from woob.browser.filters.standard import Date, BrowserURL, Format


class LoginPage(JsonPage):
    pass


class UserInfoPage(LoggedPage, JsonPage):
    def get_subscription(self, company, employee):
        subscription = Subscription()
        subscription.id = f"{employee['id']}-{company['id']}"
        subscription.label = f"{self.get('jobName')} - {self.get('companyName')}"
        subscription.subscriber = self.get('fullName')
        subscription._country = self.get('companyCountry')
        yield subscription


class AccountListPage(LoggedPage, JsonPage):
    def iter_accounts(self):
        for account in self.doc:
            employee = account["accountInfo"]
            company = account["companyInfo"]
            if "employeeId" not in account["account"]:
                continue
            employee["id"] = account["account"]["employeeId"]
            company["id"] = account["account"]["companyId"]
            yield company, employee


class DocumentsPage(LoggedPage, JsonPage):
    @method
    class iter_documents(DictElement):

        class item(ItemElement):
            klass = Document
            obj_date = Date(Dict('createdAt'))
            obj_format = Dict('type')
            obj_label = Dict('name')
            obj_id = Format("%s-%s-%s", Dict('id'), Dict('employeeId'), Dict('companyId'))
            obj_url = BrowserURL('download', id=Dict('id'))


class CategoryPage(LoggedPage, JsonPage):
    def get_id(self):
        return self.get('id')
