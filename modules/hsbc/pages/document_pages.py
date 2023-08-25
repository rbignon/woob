# Copyright(C) 2023  Powens
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

from dateutil.relativedelta import relativedelta

from woob.browser.elements import ItemElement, ListElement, TableElement, method
from woob.browser.filters.html import Attr, Link, TableCell
from woob.browser.filters.standard import CleanText, Date, Env, Field, Format
from woob.browser.pages import HTMLPage, LoggedPage, pagination, Form
from woob.capabilities.bill import Document, DocumentTypes, Subscription
from woob.tools.date import date


class MyForm(Form):
    def build(self, **kwargs):
        kwargs.setdefault('data_encoding', self.page.encoding)
        self.headers = kwargs.pop('headers', None)
        return self.page.browser.build_request(self.request, **kwargs)


class DocumentPage(LoggedPage, HTMLPage):
    FORM_CLASS = MyForm

    is_here = '//h1[text()="Relevés et documents"]'

    @method
    class iter_subscriptions(ListElement):
        # skip first because it's: "Tous les comptes"
        item_xpath = '//select[@id="select_num_compte"]/option[position()>1]'

        class item(ItemElement):
            klass = Subscription

            def condition(self):
                # Skip fake empty account added by HSBC. This account doesn't have an id
                # when selected and returns the same documents as the good one.
                return bool(CleanText('.')(self))

            obj_id = CleanText('.')
            obj__idx_account = Attr('.', 'value')

    def go_to_documents(self, idx_account, start_date, end_date=None, submit=True):
        form = self.get_form(id='statements')
        form['periode'] = '1'
        form['periode_releve'] = '0'
        form['select_fam_document'] = 'all'
        form['select_periode'] = 'def'
        form['deb_periode'] = start_date.strftime('%d/%m/%Y')

        if end_date:
            form['fin_periode'] = end_date.strftime('%d/%m/%Y')

        form['select_periode_releves'] = '0'
        form['select_num_compte'] = idx_account

        if submit:
            form.submit()
        else:
            # when used through pagination, we don't want to submit form but let pagination do it for us
            return form.build()

    @pagination
    @method
    class iter_documents(TableElement):
        # CAUTION: there are 2 tables with same id="ListCptes" on this page, yes i know
        item_xpath = '//table[@id="ListCptes"][@class="tabPlein"]/tr[position()>1]'
        head_xpath = '//table[@id="ListCptes"][@class="tabPlein"]/tr[1]/th'

        col_date = 'Date'
        col_type = 'Catégorie'
        col_label = 'Description'

        def store(self, obj):
            # This code enables doc_id when there are several docs with the exact same id
            # sometimes we have two docs on the same date
            # there is an id in the document url but it is inconsistent
            _id = obj.id
            n = 1
            while _id in self.objects:
                n += 1
                _id = f'{obj.id}-{n}'
            obj.id = _id
            self.objects[obj.id] = obj
            return obj

        class item(ItemElement):
            klass = Document

            def condition(self):
                return CleanText(TableCell('type'))(self) == 'RELEVES'

            obj_id = Format('%s_%s', Env('subid'), Field('date'))
            obj_date = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_label = Format('%s du %s', CleanText(TableCell('label')), Field('date'))
            obj_url = Link('./td[6]/a')  # can't use TableCell because this col has no text in its <th>
            obj_type = DocumentTypes.STATEMENT
            obj_format = 'pdf'

        def next_page(self):
            start_date = end_date = Date(
                Attr('//input[@name="deb_periode"]', 'value'),
                dayfirst=True
            )(self.page.doc)
            start_date -= relativedelta(years=1)

            if start_date >= date.today() - relativedelta(years=10):
                return self.page.go_to_documents(Env('idx_account')(self), start_date, end_date, submit=False)
