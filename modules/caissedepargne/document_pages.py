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


from woob.browser.elements import ItemElement, method, TableElement
from woob.browser.filters.html import Link, TableCell
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    CleanText, Date, Env, Field, Format, Regexp,
)
from woob.browser.pages import (
    HTMLPage, JsonPage, LoggedPage, Form,
)
from woob.capabilities.bill import Document, DocumentTypes, Subscription


class SubscriptionPage(LoggedPage, JsonPage):
    @method
    class get_subscription(ItemElement):
        klass = Subscription

        obj_id = Dict('subscriber/personId/id')
        obj_subscriber = Dict('subscriber/labelName')


class MyForm(Form):
    def submit(self, **kwargs):
        kwargs.setdefault('data_encoding', self.page.encoding)
        self.headers = kwargs.pop('headers', None)
        # the only change here, is location() becomes open(),
        # because we don't want to change current page
        return self.page.browser.open(self.request, **kwargs)


class DocumentsPage(LoggedPage, HTMLPage):
    FORM_CLASS = MyForm

    is_here = '//h3[@id="MM_CONSULTATION_RELEVES_COURRIERS_EDOCUMENTS_m_title"]'

    def download(self, document):
        form = self.get_form(id='main')
        form['__EVENTTARGET'] = document._event_target
        return form.submit()

    @method
    class iter_documents(TableElement):
        head_xpath = '//div[@id="MM_CONSULTATION_RELEVES_COURRIERS_EDOCUMENTS_divRelevesCourriers"]/table/thead/tr/th'
        item_xpath = '//div[@id="MM_CONSULTATION_RELEVES_COURRIERS_EDOCUMENTS_divRelevesCourriers"]/table/tbody/tr'

        col_date = 'Date'
        col_type = 'Document'

        class item(ItemElement):
            klass = Document

            def condition(self):
                return CleanText(TableCell('type'))(self) == 'Relevé de comptes'

            obj_id = Format('%s_%s', Env('subid'), Field('date'))
            obj_date = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_label = CleanText(TableCell('type'))
            obj_type = DocumentTypes.STATEMENT
            obj_format = 'pdf'
            obj__event_target = Regexp(Link('./td[6]//a'), r'WebForm_PostBackOptions\("(.*?)",')
