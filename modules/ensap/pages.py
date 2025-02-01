# Copyright(C) 2017      Juliette Fourcot
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
from woob.browser.filters.standard import BrowserURL, CleanText, Date, Env, Field, Format, Regexp
from woob.browser.pages import JsonPage, LoggedPage
from woob.capabilities.bill import Document, DocumentTypes, Subscription


class LandingPage(JsonPage):
    @property
    def logged(self):
        return self.doc["code"] == 60

    def get_message(self):
        return self.doc["message"]


class SubscriptionPage(LoggedPage, JsonPage):
    @method
    class get_subscription(ItemElement):
        klass = Subscription

        obj_id = Env("username")
        obj_subscriber = CleanText(Dict("identification/identite"))
        obj_label = Format("Account of %s", Field("subscriber"))


class YearsPage(LoggedPage, JsonPage):
    def get_years(self):
        return self.doc["listeAnnee"]


class DocumentsPage(LoggedPage, JsonPage):
    @method
    class iter_documents(DictElement):

        class item(ItemElement):
            klass = Document

            obj_id = Format("%s-%s", Regexp(Dict("libelle2"), r"(^[\w]*)"), Dict("documentUuid"))
            obj_date = Date(Dict("dateDocument"))
            obj_format = "pdf"
            obj_label = CleanText(Dict("libelle2"))
            obj_url = BrowserURL("document_download", doc_uuid=Dict("documentUuid"))
            obj_type = DocumentTypes.PAYSLIP
