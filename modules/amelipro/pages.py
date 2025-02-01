# Copyright(C) 2013-2015      Christophe Lampin
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

from dateutil.parser import parse as parse_date
from dateutil.relativedelta import relativedelta

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.html import Attr
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import BrowserURL, CleanDecimal, CleanText, Date, Env, Field, Format, Regexp
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, RawPage
from woob.capabilities.bill import Bill, Subscription


class AuthorizationPage(HTMLPage):
    def get_post_data(self):
        data = {
            "lmhidden_state": Attr('//input[@name="lmhidden_state"]', "value")(self.doc),
            "lmhidden_response_type": Attr('//input[@name="lmhidden_response_type"]', "value")(self.doc),
            "lmhidden_scope": Attr('//input[@name="lmhidden_scope"]', "value")(self.doc),
            "lmhidden_nonce": Attr('//input[@name="lmhidden_nonce"]', "value")(self.doc),
            "lmhidden_redirect_uri": Attr('//input[@name="lmhidden_redirect_uri"]', "value")(self.doc),
            "lmhidden_client_id": Attr('//input[@name="lmhidden_client_id"]', "value")(self.doc),
            "captcha_code": Attr('//input[@name="captcha_code"]', "value")(self.doc),
        }
        return data

    def get_captcha_url(self):
        return Attr('//img[@class="captcha-image"]', "src")(self.doc)

    def get_error_message(self):
        return CleanText('//div[@class="alert alert-warning alert-dismissible"]/p')(self.doc)


class SubscriptionPage(LoggedPage, HTMLPage):
    @method
    class get_subscription(ItemElement):
        klass = Subscription

        obj_id = Regexp(CleanText('//p[contains(text(), "Cabinet")]'), r"(\d+)")
        obj_label = CleanText('//div[@id="profession"]/div')
        obj_subscriber = CleanText('//div[@id="identification"]/p/b')


class DocumentsSummaryPage(LoggedPage, JsonPage):
    @method
    class iter_documents(DictElement):
        item_xpath = "value"

        class item(ItemElement):
            klass = Bill

            def condition(self):
                # Bill is "Non disponible" and has no data available
                # if pdfisable is false
                return bool(self.el["pdfisable"])

            obj_id = Format(
                "%s_%s",
                Env("subid"),
                Field("date"),
            )
            obj_label = Format("Relevé de compte du %s", Field("date"))
            obj_total_price = CleanDecimal.SI(Dict("montant"))
            obj_date = Date(CleanText(Dict("datePaiement")))
            obj_format = "pdf"
            obj_currency = "EUR"

            def obj_url(self):
                params = {
                    "datePaiement": Field("date")(self),
                    "dernierReleve": "false",
                    "typeFichier": "PDF",
                }
                return BrowserURL("releve_pdf_url", params=params)(self)


class DocumentsDetailsPage(LoggedPage, JsonPage):
    @method
    class iter_documents(DictElement):
        item_xpath = "value/lots"

        class iter_documents(ItemElement):
            klass = Bill

            # Minimal way to be unique enough
            obj_id = Format(
                "%s_%s_%s_%s",
                Env("subid"),
                Field("_num_lot"),
                Field("date"),
                Field("_code_organisme"),
            )
            obj_label = Format(
                "LOT N° %s - %s - %s - %s",
                Field("_num_lot"),
                CleanText(Dict("regime/libelle")),
                Field("_code_organisme"),
                CleanText(Dict("organisme/libelle")),
            )
            obj_total_price = CleanDecimal.SI(Dict("montantLot"))

            def obj_date(self):
                # Probably because of daylight saving time but can't be sure
                # Datetimes in this JSON are always at day -1 and 23H:00:00 compared to what
                # the website displays and uses for bills' PDF URLs
                # For example: "2022-03-30T23:00:00:000" in the JSON and "2022-03-31" on website
                return (parse_date(self.el["dateLot"]) + relativedelta(hours=1)).date()

            obj_format = "pdf"
            obj_currency = "EUR"
            obj__code_organisme = CleanText(Dict("organisme/code"))
            obj__code_regime = CleanText(Dict("organisme/codeRegime"))
            obj__num_lot = CleanText(Dict("numeroLot"))

            def obj_url(self):
                params = {
                    "codeOrganisme": Field("_code_organisme")(self),
                    "codeRegime": Field("_code_regime")(self),
                    "datePaiement": Field("date")(self),
                    "lot": Field("_num_lot")(self),
                    "typeTrie": "1",
                }
                return BrowserURL("lot_pdf_url", params=params)(self)


class RelevePDF(RawPage):
    pass


class LotPDF(RawPage):
    pass
