# Copyright(C) 2017      Baptiste Delpey
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

import re

from woob.browser.elements import ItemElement, TableElement, method
from woob.browser.filters.html import Attr, Link, TableCell
from woob.browser.filters.standard import CleanDecimal, CleanText, Currency, Field, Format, Lower, Regexp
from woob.browser.pages import HTMLPage, LoggedPage, pagination
from woob.capabilities.bank import Account
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.base import NotAvailable
from woob.tools.capabilities.bank.investments import IsinCode, IsinType


class PreMandate(LoggedPage, HTMLPage):
    def on_load(self):
        form = self.get_form()
        form.submit()


class PreMandateBis(LoggedPage, HTMLPage):
    def on_load(self):
        link = re.match("document.location.href = '([^']+)';$", CleanText('//script')(self.doc)).group(1)
        self.browser.location(link)


class MandateAccountsList(LoggedPage, HTMLPage):
    @method
    class iter_accounts(TableElement):
        item_xpath = '//table[@id="accounts"]/tbody/tr'
        head_xpath = '//table[@id="accounts"]/thead/tr/th/a'

        col_id = re.compile('N° de compte')
        col_name = 'Nom'
        col_type = 'Type'
        col_valorisation = 'Valorisation'
        col_perf = re.compile('Perf')

        class Item(ItemElement):
            TYPES = {
                'CIFO': Account.TYPE_MARKET,
                'PEA': Account.TYPE_PEA,
                'Excelis VIE': Account.TYPE_LIFE_INSURANCE,
                'Satinium': Account.TYPE_LIFE_INSURANCE,
                'Satinium CAPI': Account.TYPE_LIFE_INSURANCE,
                'Excelis CAPI': Account.TYPE_LIFE_INSURANCE,
            }

            klass = Account

            obj_id = CleanText(TableCell('id'))
            obj_label = Format('%s %s', CleanText(TableCell('type')), CleanText(TableCell('name')))
            obj_currency = Currency(TableCell('valorisation'))
            obj_bank_name = 'La Banque postale'
            obj_balance = CleanDecimal(TableCell('valorisation'), replace_dots=True)
            obj_url = Link(TableCell('id'))
            obj_iban = NotAvailable
            obj__account_holder = Lower(CleanText(TableCell('name')))

            def obj_url(self):
                td = TableCell('id')(self)[0]
                return Link(td.xpath('./a'))(self)

            def obj_type(self):
                return self.TYPES.get(CleanText(TableCell('type'))(self), Account.TYPE_UNKNOWN)


class Myiter_investments(TableElement):
    col_isin = 'Code ISIN'
    col_label = 'Libellé'
    col_unitvalue = 'Cours'
    col_valuation = 'Valorisation'


class MyInvestItem(ItemElement):
    klass = Investment

    obj_code = IsinCode(TableCell('isin'), default=NotAvailable)
    obj_code_type = IsinType(Field('code'))
    obj_label = CleanText(TableCell('label'))
    obj_quantity = CleanDecimal.French(TableCell('quantity'))
    obj_unitvalue = CleanDecimal.French(TableCell('unitvalue'))
    obj_valuation = CleanDecimal.French(TableCell('valuation'))


class MandateLife(LoggedPage, HTMLPage):
    @pagination
    @method
    class iter_investments(Myiter_investments):
        item_xpath = '//table[@id="asvSupportList"]/tbody/tr[count(td)>=5]'
        head_xpath = '//table[@id="asvSupportList"]/thead/tr/th'

        next_page = Regexp(Attr('//div[@id="turn_next"]/a', 'onclick'), 'href: "([^"]+)"')

        col_quantity = 'Quantité'

        class Item(MyInvestItem):
            pass


class MandateMarket(LoggedPage, HTMLPage):
    @method
    class iter_investments(Myiter_investments):
        # FIXME table was empty
        item_xpath = '//table[@id="valuation"]/tbody/tr[count(td)>=9]'
        head_xpath = '//table[@id="valuation"]/thead/tr/th'

        col_quantity = 'Qté'
        col_unitprice = 'Prix moyen'
        col_share = 'Poids'

        class Item(MyInvestItem):
            obj_unitprice = CleanDecimal(TableCell('unitprice'), replace_dots=True)
