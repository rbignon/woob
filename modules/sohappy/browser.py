# -*- coding: utf-8 -*-

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


from woob.browser import URL, LoginBrowser, need_login
from woob.browser.exceptions import ClientError
from woob.capabilities.bill import Bill, Detail
from woob.exceptions import BrowserIncorrectPassword

from .pages import BillPdfPage, BillsPage, ChildrenPage, LoginPage, UsersPage


class SohappyBrowser(LoginBrowser):
    BASEURL = "https://apim-production.so-happy.fr"

    login = URL(r"/api-app/tokens", LoginPage)
    bill_pdf = URL(
        r"/api-app/users/childrens/(?P<child>.*)/clients/(?P<client>.*)/bills/(?P<docid>.*)/pdf",
        BillPdfPage,
    )
    bills = URL(
        r"/api-app/users/childrens/(?P<child>.*)/clients/(?P<client>.*)/bills",
        BillsPage,
    )
    bills = URL(
        r"/api-app/users/childrens/(?P<child>.*)/clients/(?P<client>.*)/bills",
        BillsPage,
    )
    children = URL(r"/api-app/users/childrens", ChildrenPage)
    users = URL(r"/api-app/users", UsersPage)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session.headers.update(
            {
                "Ocp-Apim-Subscription-Key": "7d777a5c9c7a4def8f8e756688a0326a",
                "verbose": "true",
            }
        )

    def do_login(self):
        try:
            self.login.go(
                method="POST", json={"mail": self.username, "password": self.password}
            )
        except ClientError as exc:
            if (
                exc.response
                and exc.response.status_code == 400
                and exc.response.json()["error"]["code"] in (4001, 4005)
            ):
                raise BrowserIncorrectPassword(exc.response.json()["error"]["message"])
            raise
        self.logged = True
        self.session.headers.update(
            {"Authorization": f"Bearer {self.page.get_token()}"}
        )

    @need_login
    def get_profile(self):
        self.users.go()
        return self.page.get_profile()

    @need_login
    def get_subscription_list(self):
        self.children.go(params={"only_with_clients": "true"})
        return self.page.get_subscription_list()

    @need_login
    def iter_documents(self, subscription):
        for client in subscription.clients:
            self.bills.go(child=subscription.id, client=client)
            for document in self.page.get_document_list(
                child=subscription.id, client=client
            ):
                yield document

    @need_login
    def download_document(self, document):
        child, client, docid = document.id.split("_")
        self.bill_pdf.go(child=child, client=client, docid=docid)
        return self.page.content

    @need_login
    def get_balance(self, subscription):
        ret = Detail()
        due_bills = [
            bill.due_price
            for bill in self.iter_documents(subscription)
            if isinstance(bill, Bill) and bill.due_price
        ]
        ret.price = sum(due_bills)
        ret.currency = "€"
        ret.quantity = len(due_bills)
        return ret
