
# -*- coding: utf-8 -*-

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

from __future__ import unicode_literals

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanText, Lower, Date, Format, Regexp
from woob.browser.pages import JsonPage, LoggedPage
from woob.capabilities.bill import Document, Subscription, DocumentTypes


class HomePage(JsonPage):
    def get_error_message(self):
        return Lower(Dict('message'), transliterate=True)(self.doc)


class LoginPage(JsonPage):
    pass


class BoardPage(LoggedPage, JsonPage):
    def iter_subscription(self):
        obj = Subscription()
        obj.subscriber = Dict('identification/identite')(self.doc)
        obj.label = 'Account of %s' % obj.subscriber
        obj.id = CleanText(replace=[(' ', '.')]).filter(obj.subscriber)
        yield obj

    def get_years(self):
        return self.doc['listeAnneeRemuneration']


class DocumentsPage(LoggedPage, JsonPage):
    @method
    class iter_documents(DictElement):

        class item(ItemElement):
            klass = Document
            obj_id = Format('%s-%s', Regexp(Dict('libelle2'), r'(^[\w]*)'), Dict('documentUuid'))
            obj_date = Date(Dict('dateDocument'))
            obj_format = 'pdf'
            obj_label = Dict('nomDocument')
            obj_url = Format(
                '/prive/telechargerremunerationpaie/v1?documentUuid=%s', Dict('documentUuid')
            )
            obj_type = DocumentTypes.STATEMENT
