
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
from woob.browser.filters.standard import CleanText, Date, Format, Regexp
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage
from woob.capabilities.bill import Document, Subscription


class LoginPage(HTMLPage):
    pass


class LoginValidityPage(JsonPage):
    def check_logged(self):
        return Dict('code')(self.doc) == 60


class HomePage(LoggedPage, JsonPage):
    def iter_subscription(self):
        obj = Subscription()
        obj.subscriber = self.get('donnee.identification.identite')
        obj.label = 'Account of %s' % obj.subscriber
        obj.id = CleanText(replace=[(' ', '.')]).filter(obj.subscriber)
        yield obj


class DocumentsPage(LoggedPage, JsonPage):
    @method
    class iter_documents(DictElement):
        item_xpath = None

        class item(ItemElement):
            klass = Document
            obj_id = Format('%s-%s', Regexp(Dict('libelle2'), r'(^[\w]*)'), Dict('documentUuid'))
            obj_date = Date(Dict('dateDocument'))
            obj_format = 'pdf'
            obj_label = Dict('nomDocument')
            obj_url = Format(
                '/prive/telechargerremunerationpaie/v1?documentUuid=%s', Dict('documentUuid')
            )


class UserDataPage(LoggedPage, JsonPage):
    def get_years(self):
        return Dict('listeAnneeRemuneration')(self.doc)
