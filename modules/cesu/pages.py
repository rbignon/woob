# flake8: compatible

# Copyright(C) 2020      Ludovic LANGE
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


from urllib.parse import parse_qsl, urlparse

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import BrowserURL, CleanText, Date, Env, Field, Format, Lower, Regexp
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, RawPage
from woob.capabilities.bill import Document, DocumentTypes, Subscription


class CesuPage(HTMLPage):
    @property
    def logged(self):
        return bool(self.doc.xpath('//*[@id="deconnexion_link"]'))


class LoginPage(CesuPage):
    def is_here(self):
        return not bool(self.doc.xpath('//*[@id="deconnexion_link"]'))


class StartPage(CesuPage):
    _params = None

    @property
    def parameters(self):
        if not self._params:
            self._params = dict(parse_qsl(urlparse(self.url).query))
        return self._params


class HomePage(LoggedPage, JsonPage):
    def is_ok(self):
        return self.doc["result"] == "ok"


class CesuApiPage(LoggedPage, JsonPage):
    def get_liste_messages(self):
        return self.doc["listeMessages"]

    def has_message(self):
        return self.doc["hasMessage"]

    def has_msg_avert(self):
        return self.doc["hasMsgAvert"]

    def has_msg_err_fonc(self):
        return self.doc["hasMsgErrFonc"]

    def has_msg_err_tech(self):
        return self.doc["hasMsgErrTech"]

    def has_msg_info(self):
        return self.doc["hasMsgInfo"]

    def get_object(self):
        return self.doc.get("objet", {})

    def get_objects(self):
        return self.doc.get("listeObjets", [])


class StatusPage(CesuApiPage):
    pass


class EmployerPage(CesuApiPage):
    pass


class EmployeesPage(CesuApiPage):
    @method
    class iter_subscriptions(DictElement):
        item_xpath = "listeObjets"

        class item(ItemElement):
            klass = Subscription

            obj_id = CleanText(Dict("noIntSala"))
            obj_label = Format(
                "%s %s",
                CleanText(Dict("prenom")),
                CleanText(Dict("nom")),
            )
            obj_subscriber = Field("label")
            obj__type = "employee"


class RegistrationPage(CesuApiPage):
    @method
    class iter_documents(DictElement):
        item_xpath = "listeObjets"

        class item(ItemElement):

            def condition(self):
                return Lower(CleanText(Dict("isTelechargeable")))(self.el) == "true"

            klass = Document

            obj_id = Format("%s_%s", Env("subscription"), Dict("referenceDocumentaire"))
            obj_format = "pdf"
            obj_date = Date(Dict("dtFin"))
            obj_label = Format(
                "Bulletin de salaire %s %s %s",
                Dict("salarieDTO/prenom"),
                Dict("salarieDTO/nom"),
                Dict("periode"),
            )
            obj_type = DocumentTypes.PAYSLIP
            obj_url = BrowserURL(
                "payslip_download",
                employer=Env("employer"),
                ref_doc=Dict("referenceDocumentaire"),
            )


class RegistrationDashboardPage(CesuApiPage):
    pass


class DirectDebitSummaryPage(CesuApiPage):
    pass


class EmployeesDashboardPage(CesuApiPage):
    pass


class CurrentFiscalAdvantagePage(CesuApiPage):
    pass


class LastDayMonthPage(CesuApiPage):
    pass


class DirectDebitsHeaderPage(CesuApiPage):
    @method
    class iter_documents(DictElement):
        item_xpath = "listeObjets"

        class item(ItemElement):
            klass = Document

            obj_id = Format("%s_%s_%s", Env("subscription"), Dict("reference"), Dict("datePrelevement"))
            obj_format = "pdf"
            obj_date = Date(Dict("datePrelevement"))
            obj__period = Regexp(Dict("datePrelevement"), r"(\d{4})-(\d{2})-(\d{2})", "\\1\\2")
            obj_label = Format("Prélèvement du %s", Field("date"))
            obj_type = DocumentTypes.OTHER
            obj_url = BrowserURL(
                "direct_debit_download",
                employer=Env("employer"),
                reference=Dict("reference"),
                period=Field("_period"),
                type=Dict("typeOrigine"),
            )


class DirectDebitsDetailPage(CesuApiPage):
    pass


class DirectDebitDownloadPage(RawPage):
    pass


class TaxCertificatesPage(CesuApiPage):
    @method
    class iter_documents(DictElement):
        item_xpath = "listeObjets"

        class item(ItemElement):
            klass = Document

            obj_id = Format("%s_%s", Env("subscription"), Dict("periode"))
            obj_format = "pdf"
            obj_date = Date(Format("%s-12-31", Dict("periode")))
            obj_label = Format("Attestation fiscale %s", Dict("periode"))
            obj_type = DocumentTypes.CERTIFICATE
            obj_url = BrowserURL(
                "tax_certificate_download",
                employer=Env("employer"),
                year=Dict("periode"),
            )


class TaxCertificateDownloadPage(RawPage):
    pass


class PayslipDownloadPage(RawPage):
    pass


class FranceConnectGetUrlPage(CesuApiPage):
    def value(self):
        return self.get_object().get("redirectToFranceConnectUrl")


class FranceConnectFinalizePage(CesuApiPage):
    pass


class FranceConnectRedirectPage(RawPage):
    pass
