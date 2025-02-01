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


from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import BrowserURL, CleanText, Date, Env, Format
from woob.browser.pages import JsonPage, LoggedPage
from woob.capabilities.bill import Document, DocumentTypes, Subscription


class UserAccountsPage(LoggedPage, JsonPage):
    def iter_company_and_employee_ids(self):
        for element in self.doc:
            account = element["account"]
            if "employeeId" not in account:
                continue
            yield account["companyId"], account["employeeId"]


class UserInfoPage(LoggedPage, JsonPage):
    @method
    class get_subscription(ItemElement):
        klass = Subscription

        obj_id = Format("%s-%s", Env("employee_id"), Env("company_id"))
        obj__employee_id = Env("employee_id")
        obj__company_id = Env("company_id")
        obj_label = Format("%s - %s", CleanText(Dict("jobName")), CleanText(Dict("companyName")))
        obj_subscriber = CleanText(Dict("fullName"))
        obj__country = CleanText(Dict("companyCountry"))


class DocumentsPage(LoggedPage, JsonPage):
    @method
    class iter_documents(DictElement):

        class item(ItemElement):
            klass = Document

            obj_id = Format("%s-%s-%s", Dict("id"), Dict("employeeId"), Dict("companyId"))
            obj_date = Date(Dict("createdAt"))
            obj_format = "pdf"
            obj_label = Dict("name")
            obj_url = BrowserURL("download", id=Dict("id"))
            obj_type = DocumentTypes.PAYSLIP


class CategoryPage(LoggedPage, JsonPage):
    def get_category_id(self):
        return self.doc["id"]
