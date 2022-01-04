# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Vincent Paredes
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

import re

from woob.browser.pages import HTMLPage, LoggedPage, JsonPage, pagination
from woob.capabilities.bill import Subscription
from woob.browser.elements import DictElement, ListElement, ItemElement, method, TableElement
from woob.browser.filters.standard import (
    CleanDecimal, CleanText, Env, Field,
    Regexp, Date, Currency, BrowserURL,
    Format, Eval, Lower,
)
from woob.browser.filters.html import Link, TableCell
from woob.browser.filters.javascript import JSValue
from woob.browser.filters.json import Dict
from woob.capabilities.base import NotAvailable
from woob.capabilities.bill import DocumentTypes, Bill
from woob.tools.date import parse_french_date
from woob.tools.compat import urlencode, urlparse, parse_qsl, html_unescape


class BillsApiProPage(LoggedPage, JsonPage):
    def build_doc(self, content):
        if not content:
            return {'bills': []}  # No bills
        return super(BillsApiProPage, self).build_doc(content)

    @method
    class get_bills(DictElement):
        item_xpath = 'bills'
        # orange's API will sometimes return the temporary bill for the current month along with other bills
        # in the json. The url will lead to the exact same document, this is probably not intended behaviour and
        # causes weboob to raise a DataError as they'll have identical ids.
        ignore_duplicate = True

        class item(ItemElement):
            klass = Bill

            obj_date = Date(Dict('dueDate'), default=NotAvailable)
            obj_total_price = CleanDecimal.SI(Dict('amountIncludingTax'))
            obj_format = 'pdf'

            def obj_label(self):
                return 'Facture du %s' % Field('date')(self)

            def obj_id(self):
                return '%s_%s' % (Env('subid')(self), Field('date')(self).strftime('%d%m%Y'))

            def get_params(self):
                params = {'billid': Dict('id')(self), 'billDate': Dict('dueDate')(self)}
                return urlencode(params)

            obj_url = BrowserURL('doc_api_pro', subid=Env('subid'), dir=Dict('documents/0/mainDir'), fact_type=Dict('documents/0/subDir'), billparams=get_params)
            obj__is_v2 = False


class BillsApiParPage(LoggedPage, JsonPage):
    def build_doc(self, content):
        if not content:
            return {'billsHistory': {'billList': []}}  # No bills
        return super(BillsApiParPage, self).build_doc(content)

    @method
    class get_bills(DictElement):
        item_xpath = 'billsHistory/billList'

        def condition(self):
            return (
                Dict('billsHistory', default=None)(self) and
                Dict('billsHistory/billList', default=None)(self)
            )

        class item(ItemElement):
            klass = Bill

            obj_date = Date(Dict('date'), default=NotAvailable)
            obj_price = Eval(lambda x: x / 100, CleanDecimal(Dict('amount')))
            obj_format = 'pdf'

            def obj_label(self):
                return 'Facture du %s' % Field('date')(self)

            def obj_id(self):
                return '%s_%s' % (Env('subid')(self), Field('date')(self).strftime('%d%m%Y'))

            obj_url = Format('%s%s', BrowserURL('doc_api_par'), Dict('hrefPdf'))
            obj__is_v2 = True


# is BillsPage deprecated ?
class BillsPage(LoggedPage, HTMLPage):
    def on_load(self):
        # There is a small chance that this Page is still used if we are redirected
        # to it after requesting bills_api_par and bills_api_pro since the method
        # to collect the bills has the same name
        # TODO remove this class in a few days if the message below is not showing up
        #  or remove the on_load otherwise
        self.logger.warning('Orange legacy BillsPage still active')

    @method
    class get_bills(TableElement):
        item_xpath = '//table[has-class("table-hover")]/div/div/tr | //table[has-class("table-hover")]/div/tr'
        head_xpath = '//table[has-class("table-hover")]/thead/tr/th'

        col_date = 'Date'
        col_amount = ['Montant TTC', 'Montant']
        col_ht = 'Montant HT'
        col_url = 'Télécharger'
        col_infos = 'Infos paiement'

        class item(ItemElement):
            klass = Bill

            obj_type = DocumentTypes.BILL
            obj_format = "pdf"

            # TableCell('date') can have other info like: 'duplicata'
            obj_date = Date(CleanText('./td[@headers="ec-dateCol"]/text()[not(preceding-sibling::br)]'), parse_func=parse_french_date, dayfirst=True)

            def obj__cell(self):
                # sometimes the link to the bill is not in the right column (Thanks Orange!!)
                if CleanText(TableCell('url')(self))(self):
                    return 'url'
                return 'infos'

            def obj_price(self):
                if CleanText(TableCell('amount')(self))(self):
                    return CleanDecimal(Regexp(CleanText(TableCell('amount')), '.*?([\d,]+).*', default=NotAvailable), replace_dots=True, default=NotAvailable)(self)
                else:
                    return Field('_ht')(self)

            def obj_currency(self):
                if CleanText(TableCell('amount')(self))(self):
                    return Currency(TableCell('amount')(self))(self)
                else:
                    return Currency(TableCell('ht')(self))(self)

            # Only when a list of documents is present
            obj__url_base = Regexp(CleanText('.//ul[@class="liste"]/script', default=None), '.*?contentList[\d]+ \+= \'<li><a href=".*\"(.*?idDocument=2)"', default=None)

            def obj_url(self):
                if Field('_url_base')(self):
                    # URL won't work if HTML is not unescape
                    return html_unescape(str(Field('_url_base')(self)))
                return Link(TableCell(Field('_cell')(self))(self)[0].xpath('./a'), default=NotAvailable)(self)

            obj__label_base = Regexp(CleanText('.//ul[@class="liste"]/script', default=None), '.*</span>(.*?)</a.*', default=None)

            def obj_label(self):
                if Field('_label_base')(self):
                    return html_unescape(str(Field('_label_base')(self)))
                else:
                    return CleanText(TableCell(Field('_cell')(self))(self)[0].xpath('.//span[@class="ec_visually_hidden"]'))(self)

            obj__ht = CleanDecimal(TableCell('ht', default=NotAvailable), replace_dots=True, default=NotAvailable)

            def obj_vat(self):
                if Field('_ht')(self) is NotAvailable or Field('price')(self) is NotAvailable:
                    return
                return Field('price')(self) - Field('_ht')(self)

            def obj_id(self):
                if Field('price')(self) is NotAvailable:
                    return '%s_%s%s' % (Env('subid')(self), Field('date')(self).strftime('%d%m%Y'), Field('_ht')(self))
                else:
                    return '%s_%s%s' % (Env('subid')(self), Field('date')(self).strftime('%d%m%Y'), Field('price')(self))


class SubscriptionsPage(LoggedPage, HTMLPage):
    def build_doc(self, data):
        data = data.decode(self.encoding)
        for line in data.split('\n'):
            mtc = re.match('necFe.bandeau.container.innerHTML\s*=\s*stripslashes\((.*)\);$', line)
            if mtc:
                html = JSValue().filter(mtc.group(1)).encode(self.encoding)
                return super(SubscriptionsPage, self).build_doc(html)

    @method
    class iter_subscription(ListElement):
        item_xpath = '//ul[@id="contractContainer"]//a[starts-with(@id,"carrousel-")]'

        class item(ItemElement):
            klass = Subscription

            obj_id = Regexp(Link('.'), r'\bidContrat=(\d+)', default='')
            obj__page = Regexp(Link('.'), r'\bpage=([^&]+)', default='')
            obj_label = CleanText('.')
            obj__is_pro = False

            def validate(self, obj):
                # unsubscripted contracts may still be there, skip them else
                # facture-historique could yield wrong bills
                return bool(obj.id) and obj._page != 'nec-tdb-ouvert'


class SubscriptionsApiPage(LoggedPage, JsonPage):
    @method
    class iter_subscription(DictElement):
        item_xpath = 'contracts'

        class item(ItemElement):
            klass = Subscription

            obj_id = Dict('contractId')
            obj_label = Dict('offerName')
            obj__is_pro = False


class ContractsPage(LoggedPage, JsonPage):
    @pagination
    @method
    class iter_subscriptions(DictElement):
        item_xpath = 'contracts'

        def next_page(self):
            params = dict(parse_qsl(urlparse(self.page.url).query))
            page_number = int(params['page'])
            nbcontractsbypage = int(params['nbcontractsbypage'])
            nb_subs = page_number * nbcontractsbypage

            # sometimes totalContracts can be different from real quantity
            # already seen totalContracts=39 with 38 contracts in json
            # so we compare nb contracts received in this response with number per page to make sure we stop
            # even if there is oneday totalContracts=7677657689 but just 8 contracts
            doc = self.page.doc
            if nb_subs < doc['totalContracts'] and len(doc['contracts']) == nbcontractsbypage:
                params['page'] = page_number + 1
                return self.page.browser.contracts.build(params=params)

        class item(ItemElement):
            klass = Subscription

            obj_id = Dict('id')
            obj_label = Format('%s %s', Dict('name'), Dict('mainLine'))
            obj__from_api = False

            def condition(self):
                return Dict('status')(self) == 'OK'

            def obj__is_pro(self):
                return Dict('offerNature')(self) == 'PROFESSIONAL'


class ContractsApiPage(LoggedPage, JsonPage):
    @method
    class iter_subscriptions(DictElement):
        item_xpath = 'contracts'

        class item(ItemElement):
            klass = Subscription

            obj_id = CleanText(Dict('cid'))
            obj_label = Dict('offerName')

            def obj_subscriber(self):
                names = (
                    CleanText(Dict('holder/firstName', default=""))(self),
                    CleanText(Dict('holder/lastName', default=""))(self),
                )
                if not any(names):
                    return NotAvailable
                return ' '.join([n for n in names if n])

            def obj__is_pro(self):
                return Dict('telco/marketType', default='PAR')(self) == 'PRO'

            obj__from_api = True

            def condition(self):
                return Lower(Dict('status'))(self) == 'actif'
