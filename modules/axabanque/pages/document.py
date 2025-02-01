# Copyright(C) 2010-2017 Théo Dorée
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
from woob.browser.filters.standard import BrowserURL, CleanText, Date, Env, Eval, Field, Format, Map
from woob.browser.pages import JsonPage, LoggedPage
from woob.capabilities.bill import Document, DocumentTypes, Subscription


class SubscriptionsPage(LoggedPage, JsonPage):
    @method
    class iter_subscriptions(DictElement):
        class item(ItemElement):
            klass = Subscription

            obj_id = Dict("sourceContractId")

            # there can be several "participants" but no matter what _contract_id is,
            # list of related documents will be the same, so we can simply take the first one
            obj__contract_id = Dict("participants/0/id")  # CAUTION non persistant
            obj_subscriber = Format(
                "%s %s",
                CleanText(Dict("participants/0/firstName")),
                CleanText(Dict("participants/0/lastName")),
            )


DOCUMENT_TYPES = {
    "Relevé de compte": DocumentTypes.STATEMENT,
    "e-relevés": DocumentTypes.STATEMENT,
}


class MyDictElement(DictElement):
    # obj.id is based on documentName field, but we can have several documents with same name
    # their pdf is really not the same, so it's really different documents
    # we have to add a number to obj.id in that case
    #  document_name
    #  document_name-2
    #  document_name-3
    # etc...
    def store(self, obj):
        _id = obj.id
        n = 1
        while _id in self.objects:
            n += 1
            _id = f"{obj.id}-{n}"
        obj.id = _id
        self.objects[obj.id] = obj
        return obj


class DocumentsPage(LoggedPage, JsonPage):
    @method
    class iter_documents(MyDictElement):
        class item(ItemElement):
            klass = Document

            obj_id = Format("%s_%s", Env("subid"), Field("_doc_name"))
            obj_label = CleanText(Dict("documentName"))
            obj_date = Date(CleanText(Dict("depositDate")))
            obj_type = Map(Dict("typeLabel"), DOCUMENT_TYPES, DocumentTypes.OTHER)
            obj_url = BrowserURL("document_pdf", contract_id=Env("contract_id"), document_id=Dict("documentId"))
            obj__doc_name = Eval(lambda v: v.strip(".pdf"), Dict("documentName"))
            obj_format = "pdf"
