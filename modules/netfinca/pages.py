# -*- coding: utf-8 -*-

# Copyright(C) 2012-2019  Budget-Insight
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import re
import datetime

from weboob.browser.pages import HTMLPage, LoggedPage
from weboob.browser.elements import method, ItemElement, TableElement
from weboob.browser.filters.standard import (
    CleanText, CleanDecimal, Currency, Map, MapIn,
    Field, Regexp, Base, Date, Coalesce,
)
from weboob.browser.filters.html import TableCell, Attr, Link
from weboob.capabilities.bank import Account
from weboob.capabilities.wealth import (
    Investment, MarketOrder, MarketOrderType,
    MarketOrderDirection, MarketOrderPayment,
)
from weboob.capabilities.base import NotAvailable, empty
from weboob.tools.capabilities.bank.investments import (
    is_isin_valid, create_french_liquidity, IsinCode, IsinType,
)


ACCOUNT_TYPES = {
    'D.A.T.': Account.TYPE_DEPOSIT,
    'COMPTE PEA': Account.TYPE_PEA,
    'INTEGRAL PEA': Account.TYPE_PEA,
    'COMPTE PEA-PME': Account.TYPE_PEA,
    'INTEGRAL C.T.O.': Account.TYPE_MARKET,
    'COMPTE TITRES': Account.TYPE_MARKET,
    'CTO VENDOME PRIVILEGE': Account.TYPE_MARKET,
    'PARTS SOCIALES': Account.TYPE_MARKET,
    'PEA VENDOME PATRIMOINE': Account.TYPE_PEA,
}


class AccountsPage(LoggedPage, HTMLPage):
    # UTF8 tag in the meta div, but that's wrong
    ENCODING = 'iso-8859-1'

    @method
    class iter_accounts(TableElement):

        head_xpath = '//table[contains(@class,"tableau_comptes_details")]//th'

        # There is not 'tbody' balise in the table, we have to get all tr and get out thead and tfoot ones
        item_xpath = '//table[contains(@class,"tableau_comptes_details")]//tr[not(ancestor::thead) and not(ancestor::tfoot)]'

        col_id = col_label = 'Comptes'
        col_owner = 'Titulaire du compte'
        col_balance = re.compile(r'.*Valorisation totale.*')

        class item(ItemElement):
            klass = Account

            obj_type = Map(Field('label'), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)
            obj__owner = CleanText(TableCell('owner'))

            def obj_id(self):
                tablecell = TableCell('id')(self)[0]
                _id = tablecell.xpath('./div[position()=2]')
                return CleanText(_id)(self)

            obj_number = obj_id

            def obj_label(self):
                tablecell = TableCell('label')(self)[0]
                label = tablecell.xpath('./div[position()=1]')
                return CleanText(label)(self)

            def obj_balance(self):
                tablecell = TableCell('balance')(self)[0]
                balance = tablecell.xpath('./span[@class="intraday"]')
                return CleanDecimal.French(balance)(self)

            def obj_currency(self):
                tablecell = TableCell('balance')(self)[0]
                currency = tablecell.xpath('./span[@class="intraday"]')
                return Currency(currency)(self)

    def get_action_needed_message(self):
        return CleanText('//form[@id="profilForm"]')(self.doc)

    def is_account_present(self, account_id):
        return Attr('//td[contains(@id, "wallet-%s")]' % account_id, 'onclick', default=None)(self.doc)

    def get_nump_id(self, account):
        # Return an element needed in the request in order to access investments details
        attr = Attr('//td[contains(@id, "wallet-%s")]' % account.id, 'onclick')(self.doc)
        return re.search('([0-9]+:[0-9]+)', attr).group(1)


class InvestmentsPage(LoggedPage, HTMLPage):

    # UTF8 tag in the meta div, but that's wrong
    ENCODING = 'iso-8859-1'

    @method
    class get_investments(TableElement):

        item_xpath = '//table[@id="tableValeurs"]/tbody/tr[starts-with(@id, "ContentDetPosInLine")]'
        head_xpath = '//table[@id="tableValeurs"]/thead//th'

        col_label = col_code = 'Valeur / Isin'
        col_quantity = ['Quantité', 'Qté']
        col_unitvalue = col_vdate = 'Cours'
        col_valuation = ['Valorisation totale', 'Val. totale']
        col_unitprice = 'Prix de revient'
        col_diff = '+/- Value latente'

        # Due to a bug in TableCell, column's number match with tdcell-1
        # Had to use <following-sibling::td[position()=1]> each time in xpath to get the right cell
        # @todo : Correct the TableCell class and this module

        class item(ItemElement):
            klass = Investment

            obj_valuation = CleanDecimal.French(TableCell('valuation'))

            def obj_diff(self):
                tablecell = TableCell('diff', default=NotAvailable)(self)
                if empty(tablecell):
                    return NotAvailable
                return CleanDecimal.French(TableCell('diff'), default=NotAvailable)(self)

            # Some invests have a format such as '22,120' but some others have '0,7905 (79,05%)'
            def obj_unitprice(self):
                tablecell = TableCell('unitprice', default=NotAvailable)(self)
                if empty(tablecell):
                    return NotAvailable
                return CleanDecimal.French(
                    Regexp(
                        CleanText(TableCell('unitprice')),
                        r'([0-9]+,[0-9]+)',
                        default=NotAvailable
                    ),
                    default=NotAvailable
                )(self)

            def obj_quantity(self):
                tablecell = TableCell('quantity', default=NotAvailable)(self)
                if empty(tablecell):
                    return NotAvailable
                elif '€' in Base(tablecell, CleanText('./span'))(self):
                    # Euro funds only have the amount invested (in euros) in this column
                    return NotAvailable
                return Base(tablecell, CleanDecimal.French('./span'))(self)

            def obj_label(self):
                tablecell = TableCell('label')(self)[0]
                tablecell_values = tablecell.xpath('./following-sibling::td[@class=""]/div/a')
                if tablecell_values:
                    return CleanText(tablecell_values[0])(self)
                # In rare cases the last invest of the table has a different <td> class name
                return CleanText(tablecell.xpath('./following-sibling::td[has-class("last")]/div/a')[0])(self)

            def obj_code(self):
                # We try to get the code from <a> div. If we didn't find code in url,
                # we try to find it in the cell text
                tablecell = TableCell('label')(self)[0]
                # url find try
                code_match = Regexp(
                    Link(tablecell.xpath('./following-sibling::td[position()=1]/div/a')),
                    r'sico=([A-Z0-9]*)',
                    default=None
                )(self)
                if is_isin_valid(code_match):
                    return code_match

                # cell text find try
                text = CleanText(tablecell.xpath('./following-sibling::td[position()=1]/div')[0])(self)

                for code in text.split(' '):
                    if is_isin_valid(code):
                        return code
                return NotAvailable

            obj_code_type = IsinType(Field('code'), default=NotAvailable)

            def obj_unitvalue(self):
                currency, unitvalue = self.original_unitvalue()
                if currency == self.env['account_currency']:
                    return unitvalue
                return NotAvailable

            def obj_original_currency(self):
                currency, unitvalue = self.original_unitvalue()

                if currency != self.env['account_currency']:
                    return currency

            def obj_original_unitvalue(self):
                currency, unitvalue = self.original_unitvalue()

                if currency != self.env['account_currency']:
                    return unitvalue

            def obj_vdate(self):
                tablecell = TableCell('vdate', default=NotAvailable)(self)
                if empty(tablecell):
                    return NotAvailable
                vdate_scraped = tablecell[0].xpath('./preceding-sibling::td[position()=1]//span/text()')[0]

                # Scraped date could be a schedule time (00:00) or a date (01/01/1970)
                vdate = NotAvailable

                if ':' in vdate_scraped:
                    today = datetime.date.today()
                    h, m = [int(x) for x in vdate_scraped.split(':')]
                    hour = datetime.time(hour=h, minute=m)
                    vdate = datetime.datetime.combine(today, hour)

                elif '/' in vdate_scraped:
                    vdate = datetime.datetime.strptime(vdate_scraped, '%d/%m/%y')

                return vdate

            # extract unitvalue and currency
            def original_unitvalue(self):
                tablecell = TableCell('unitvalue', default=NotAvailable)(self)
                if empty(tablecell):
                    return (NotAvailable, NotAvailable)

                text = Base(tablecell, CleanText('.'))(self)
                if '%' in text:
                    # For euro funds, the unit_value is replaced by a diff percentage
                    return (NotAvailable, NotAvailable)
                return (
                    Base(tablecell, Currency('.', default=NotAvailable))(self),
                    Base(tablecell, CleanDecimal.French('.', default=NotAvailable))(self)
                )

    def get_liquidity(self):
        # Not all accounts have a Liquidity element
        liquidity_element = CleanDecimal.French('//td[contains(text(), "Solde espèces en euros")]//following-sibling::td[position()=1]', default=None)(self.doc)
        if liquidity_element:
            return create_french_liquidity(liquidity_element)


MARKET_ORDER_DIRECTIONS = {
    'Vente': MarketOrderDirection.SALE,
    'Achat': MarketOrderDirection.BUY,
}


MARKET_ORDER_PAYMENTS = {
    'Comptant': MarketOrderPayment.CASH,
    'SRD': MarketOrderPayment.DEFERRED,
}


class MarketOrdersPage(LoggedPage, HTMLPage):
    # UTF8 tag in the meta div, but that's wrong
    ENCODING = 'iso-8859-1'

    def has_no_order(self):
        return CleanText('//table[@id="orderListTable"]//td[contains(text(), "aucun ordre")]')(self.doc)

    def get_next_pages(self):
        next_pages = []
        for page in self.doc.xpath('//span/@data-page'):
            next_pages.append(CleanText().filter(page))
        return next_pages

    @method
    class iter_market_orders(TableElement):
        head_xpath = '//table[@id="orderListTable"]//thead//th'
        item_xpath = '//table[@id="orderListTable"]//tbody//tr'

        col__details_link = 'Détails'
        col_date = 'Date de création'
        col_label = 'Libellé'
        col_direction = 'Sens'
        col_quantity = 'Qté'
        col_limit = 'Limite'
        col_trigger = 'Seuil'
        col_state = 'Etat'
        col_amount = 'Montant'
        col_validity_date = 'Date de validité'

        class item(ItemElement):
            klass = MarketOrder

            obj__details_link = Base(TableCell('_details_link'), Link('.//a'))
            obj_label = Base(TableCell('label'), CleanText('.//a/@title'))
            obj_direction = MapIn(CleanText(TableCell('direction')), MARKET_ORDER_DIRECTIONS, MarketOrderDirection.UNKNOWN)
            obj_state = CleanText(TableCell('state'))
            obj_date = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_validity_date = Date(CleanText(TableCell('validity_date')), dayfirst=True, default=NotAvailable)
            obj_quantity = CleanDecimal.French(TableCell('quantity'), default=NotAvailable)
            # Extract the unitprice from the state (e.g. 'Exécuté à 58,70 € <sometimes additional text>')
            obj_unitprice = CleanDecimal.French(
                Regexp(CleanText(TableCell('state')), r'Exécuté à ([\d ,]+)', default=NotAvailable),
                default=NotAvailable
            )

            def obj_order_type(self):
                # The column containing the value depends on the order type.
                if CleanText(TableCell('limit'))(self) not in ('', '-'):
                    return MarketOrderType.LIMIT
                if CleanText(TableCell('trigger'))(self) not in ('', '-'):
                    return MarketOrderType.TRIGGER
                # If there is no limit or trigger value, we type the order as MARKET
                return MarketOrderType.MARKET

            # Ordervalue is not in the same column depending on the order_type
            obj_ordervalue = Coalesce(
                CleanDecimal.French(TableCell('limit'), default=NotAvailable),
                CleanDecimal.French(TableCell('trigger'), default=NotAvailable),
                default=NotAvailable
            )

            # ISIN code is hidden in a script such as "javascript:goQuote('LU1681046261', '012')"
            obj_code = IsinCode(
                Regexp(
                    Base(TableCell('label'), CleanText('.//a/@href')),
                    r"Quote\('([^']*)'",
                    default=NotAvailable
                ),
                default=NotAvailable
            )

    @method
    class fill_market_order(ItemElement):
        obj_id = CleanText('//td[contains(text(), "Référence Bourse")]/following-sibling::td[1]', default=NotAvailable)
        obj_currency = Currency('//td[contains(text(), "Devise")]/following-sibling::td[1]', default=NotAvailable)
        obj_amount = CleanDecimal.French(
            '//td[contains(text(), "Total")]/following-sibling::td[1]',
            default=NotAvailable
        )
        obj_payment_method = Map(
            CleanText('//td[contains(text(), "Règlement")]/following-sibling::td[1]'),
            MARKET_ORDER_PAYMENTS,
            MarketOrderPayment.UNKNOWN
        )

        def obj_stock_market(self):
            # For some reason they tend to randomly add 'Meilleure Exécution',
            # with or without parenthesis
            raw_value = CleanText(
                '//td[contains(text(), "Place")]/following-sibling::td[1]',
                replace=[('(', ''), ('Meilleure exécution', ''), (')', '')],
                default=NotAvailable
            )(self)
            return raw_value or NotAvailable
