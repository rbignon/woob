# Copyright(C) 2024      Ludovic LANGE
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

import re

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    BrowserURL,
    CleanDecimal,
    CleanText,
    Coalesce,
    Date,
    Env,
    Eval,
    Field,
    Format,
    Map,
    Regexp,
)
from woob.browser.pages import JsonPage, LoggedPage
from woob.capabilities.bill import Document, DocumentTypes, Subscription
from woob.tools.capabilities.bank.transactions import FrenchTransaction


class RibPage(LoggedPage, JsonPage):
    def get_iban(self):
        return Dict("iban")(self.doc)


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
    "Relevé de Compte": DocumentTypes.STATEMENT,
    "Courrier libre client": DocumentTypes.NOTICE,
    "Recapitulatif Annuel des Frais": DocumentTypes.REPORT,
    "Relevé Loi Chatel": DocumentTypes.BILL,
    "Courrier Garantie dépôts (FGDR)": DocumentTypes.NOTICE,
}


class Transaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r"^CARTE (?P<dd>\d{2})/(?P<mm>\d{2}) (?P<text>.*)"), FrenchTransaction.TYPE_CARD),
        (re.compile(r"^(?P<text>(PRLV|PRELEVEMENTS).*)"), FrenchTransaction.TYPE_ORDER),
        (re.compile(r"^(?P<text>RET DAB.*)"), FrenchTransaction.TYPE_WITHDRAWAL),
        (re.compile(r"^(?P<text>ECH.*)"), FrenchTransaction.TYPE_LOAN_PAYMENT),
        (re.compile(r"^(?P<text>VIR.*)"), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r"^(?P<text>ANN.*)"), FrenchTransaction.TYPE_PAYBACK),
        (re.compile(r"^(?P<text>(VRST|VERSEMENT).*)"), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r"^(?P<text>CHQ.*)"), FrenchTransaction.TYPE_CHECK),
        (re.compile(r"^(?P<text>.*)"), FrenchTransaction.TYPE_BANK),
    ]


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

            obj_id = Format("%s_%s", Env("subid"), Dict("Id"))
            obj_label = CleanText(Field("_doc_name"))
            obj_date = Date(CleanText(Dict("depositDate")))
            obj_type = Map(Dict("documentType"), DOCUMENT_TYPES, DocumentTypes.OTHER)
            obj_url = BrowserURL("document_pdf", database=Dict("dataBase"), document_id=Dict("Id"))
            obj__doc_name = Eval(lambda v: v.strip(".pdf"), Dict("documentName"))
            obj_format = "pdf"


class TransactionsPage(LoggedPage, JsonPage):
    @method
    class iter_transactions(DictElement):
        class item(ItemElement):
            klass = Transaction
            obj_id = Regexp(Dict("id"), r"^(.*?)[_=]*$", "\\1")
            obj_original_currency = Dict("currency")
            obj_amount = CleanDecimal.SI(Dict("amount"))
            obj_date = Date(Dict("bookedDate"))
            obj_rdate = Date(Dict("transactionDate"))
            obj_vdate = Date(Dict("valueDate"))
            obj_raw = Transaction.Raw(Dict("longLabel"))
            obj_coming = Coalesce(Eval(lambda x: x != "booked", Dict("type")), default=False)
