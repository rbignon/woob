# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Jocelyn Jaubert
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

from woob.capabilities.bill import Document, DocumentTypes
from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.standard import CleanText, Date, Format, Field, BrowserURL, Env, Eval
from woob.browser.filters.json import Dict
from woob.browser.pages import LoggedPage, RawPage, JsonPage


def parse_from_timestamp(date, **kwargs):
    # divide by 1000 because given value is a millisecond timestamp
    return datetime.fromtimestamp(int(date) / 1000)


class DocumentsPage(LoggedPage, JsonPage):
    def has_documents(self):
        return bool(self.doc['donnees']['edocumentDto']['listCleReleveDto'])

    @method
    class iter_documents(DictElement):
        item_xpath = 'donnees/edocumentDto/listCleReleveDto'

        class item(ItemElement):
            klass = Document

            obj_id = Format('%s_%s', Env('subid'), Dict('referenceTechniqueEncode'))
            obj_label = Format(
                '%s au %s',
                CleanText(Dict('labelReleve')),
                Eval(lambda x: x.strftime('%d/%m/%Y'), Field('date'))
            )
            obj_date = Date(CleanText(Dict('dateArrete')), parse_func=parse_from_timestamp)
            obj_type = DocumentTypes.STATEMENT
            obj_format = 'pdf'
            # this url is stateful and has to be called when we are on
            # the right page with the right range of 3 months
            # else we get a 302 to /page-indisponible
            obj_url = BrowserURL(
                'pdf_page',
                id_tech=Dict('idTechniquePrestation'),
                ref_tech=Dict('referenceTechniqueEncode')
            )


class RibPdfPage(LoggedPage, RawPage):
    pass
