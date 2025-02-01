# Copyright(C) 2012-2020  Budget Insight
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

from datetime import datetime
from decimal import Decimal

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.html import Attr
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanText, Date, Env, Eval, Format
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, RawPage
from woob.capabilities.base import NotAvailable
from woob.capabilities.bill import Bill, Subscription
from woob.capabilities.profile import Profile

from .akamai import AkamaiHTMLPage


class HomePage(HTMLPage):
    pass


class XUIPage(AkamaiHTMLPage):
    pass


class AuthenticatePage(JsonPage):
    def has_captcha_request(self):
        return self.doc["stage"] == "RecaptchaModuleS1"

    def get_data(self):
        return self.doc

    def get_token(self):
        return self.doc["tokenId"]


class AuthorizePage(HTMLPage):
    def on_load(self):
        if Attr("//body", "onload", default=NotAvailable)(self.doc):
            self.get_form().submit()


class WrongPasswordPage(HTMLPage):
    def get_wrongpass_message(self, attempt_number):
        # edf website block access after 5 wrong password, and user will have to change his password
        # this is very important because it can tell to user how much attempt it remains
        msg = CleanText('//p[@id="error1"]')(self.doc)
        msg_remain_attemp = CleanText('//p[strong[@id="attempt-number"]]', default="")(self.doc)
        msg_remain_attemp = msg_remain_attemp.replace("{{theme.settings.spaceName.texte}} ", "")

        if attempt_number > 0:
            msg += " " + msg_remain_attemp.replace(
                "Tentatives restantes : X", "Tentatives restantes : %d" % attempt_number
            )

        return msg


class OTPTemplatePage(HTMLPage):
    def get_otp_message(self):
        return CleanText('//main[has-class("auth__content")]/h2', children=False)(self.doc)


class WelcomePage(LoggedPage, HTMLPage):
    pass


class CheckAuthenticatePage(LoggedPage, RawPage):
    pass


class UnLoggedPage(HTMLPage):
    pass


class ProfilPage(JsonPage):
    @property
    def logged(self):
        return self.doc["errorCode"] == 0

    @method
    class iter_subscriptions(DictElement):
        item_xpath = "customerAccordContracts"

        class item(ItemElement):
            klass = Subscription

            obj_subscriber = Format("%s %s", Dict("bp/identity/firstName"), Dict("bp/identity/lastName"))
            obj_id = Dict("number")
            obj_label = obj_id

    def get_token(self):
        return Dict("data")(self.doc)


class DocumentsPage(LoggedPage, JsonPage):
    @method
    class iter_bills(DictElement):
        def parse(self, el):
            for i, sub_group in enumerate(self.el):
                for j, sub in enumerate(Dict("listOfBillsByAccDTO")(sub_group)):
                    if Dict("accDTO/numAcc")(sub) in Env("subid")(self):
                        self.item_xpath = "%d/listOfBillsByAccDTO/%d/listOfbills" % (i, j)
                        self.env["bpNumber"] = Dict("%d/bpDto/bpNumber" % i)(self)
                        break

        class item(ItemElement):
            klass = Bill

            obj_id = Format("%s_%s", Env("subid"), Dict("documentNumber"))
            obj_date = Date(
                Eval(lambda t: datetime.fromtimestamp(int(t) / 1000).strftime("%Y-%m-%d"), Dict("creationDate"))
            )
            obj_format = "pdf"
            obj_label = Format("Facture %s", Dict("documentNumber"))
            obj_price = Env("price")
            obj_currency = "EUR"
            obj_vat = NotAvailable
            obj__doc_number = Dict("documentNumber")
            obj__par_number = Dict("parNumber")
            obj__num_acc = Env("numAcc")
            obj__bp = Env("bpNumber")

            def parse(self, el):
                self.env["price"] = Decimal(Dict("billAmount")(self))
                self.env["numAcc"] = str(int(Env("subid")(self)))

    def get_bills_informations(self):
        return {
            "bpNumber": Dict("bpNumber")(self.doc),
            "docId": Dict("docId")(self.doc),
            "docName": Dict("docName")(self.doc),
            "numAcc": Dict("numAcc")(self.doc),
            "parNumber": Dict("parNumber")(self.doc),
        }


class ProfilePage(LoggedPage, JsonPage):
    def get_profile(self):
        data = self.doc["bp"]
        profile = Profile()

        profile.address = "{} {} {} {}".format(
            data["streetNumber"],
            data["streetName"],
            data["postCode"],
            data["city"],
        )
        profile.name = "{} {} {}".format(data["civility"], data["lastName"], data["firstName"])
        profile.phone = data["mobilePhoneNumber"] or data["fixPhoneNumber"]
        profile.email = data["mail"]

        return profile


class BillDownload(LoggedPage, RawPage):
    pass
