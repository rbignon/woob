# Copyright(C) 2022      Guillaume Thomas
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

from woob.browser.pages import JsonPage, LoggedPage, RawPage
from woob.capabilities.base import Field, FloatField
from woob.capabilities.bill import Bill, Subscription
from woob.capabilities.profile import Profile
from woob.tools.date import parse_french_date


class LoginPage(JsonPage):
    def get_token(self):
        return self.get("token.value")


class UsersPage(LoggedPage, JsonPage):
    def get_profile(self):
        profile = Profile(id=self.get("id"))
        profile.name = self.get("first_name") + " " + self.get("last_name")
        profile.email = self.get("mail")
        profile.phone = self.get("phone")
        return profile


class SoHappySubscription(Subscription):
    """
    SoHappy Subscription.
    """

    clients = Field("clients", list)


class ChildrenPage(LoggedPage, JsonPage):
    def get_subscription_list(self):
        ret = []
        for child in self.response.json():
            subscription = SoHappySubscription(id=child["id"])
            subscription.label = child["first_name"]
            subscription.clients = [client["id"] for client in child["clients"]]
            ret.append(subscription)
        return ret


class SoHappyBill(Bill):
    total_price = FloatField("Price to pay")
    due_price = FloatField("Price due")


class BillsPage(LoggedPage, JsonPage):
    def get_document_list(self, child, client):
        ret = []
        for item in self.response.json():
            item_id = item["id"]
            bill = SoHappyBill(id=f"{child}_{client}_{item_id}")
            bill.has_file = item["has_pdf"]
            bill.format = "pdf"
            bill.label = item["publication_label"]
            bill.date = parse_french_date(item["publication_label"])
            bill.date = bill.date.replace(day=1)
            bill.total_price = item["amount"]["total"]
            bill.due_price = item["amount"]["to_pay"]
            bill.currency = "€"
            ret.append(bill)
        return ret


class BillPdfPage(LoggedPage, RawPage):
    pass
