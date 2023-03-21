# Copyright(C) 2023 Powens
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

from hashlib import sha256

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanText, Env, FromTimestamp
from woob.browser.pages import JsonPage, LoggedPage, RawPage, pagination
from woob.capabilities.bill import Document, DocumentTypes
from woob.tools.url import get_url_params


class DocumentsPage(LoggedPage, JsonPage):
    @pagination
    @method
    class iter_documents(DictElement):
        def next_page(self):
            if not self.page.doc:
                # no element here, we have very probably reached the very beginning
                return

            params = get_url_params(self.page.browser.url)
            start = int(params['start'])
            end = int(params['end'])
            diff = end - start

            end = start
            start -= diff

            params['start'] = str(start)
            params['end'] = str(end)

            return self.page.browser.documents_page.build(params=params)

        class item(ItemElement):
            klass = Document

            def obj_id(self):
                _id = CleanText(Dict('id'))(self)
                # this id may be very long, we encode it to make sure it's not too big
                val = sha256(_id.encode('utf-8')).hexdigest()
                return Env('subid')(self) + '_' + val

            obj_label = CleanText(Dict('fileName'))
            obj_type = DocumentTypes.STATEMENT
            obj_date = FromTimestamp(Dict('creationDateTimestamp'), millis=True)
            obj_format = 'pdf'
            obj__download_id = CleanText(Dict('id'))


class PdfPage(RawPage):
    pass
