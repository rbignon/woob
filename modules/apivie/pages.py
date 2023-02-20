# Copyright(C) 2013      Romain Bignon
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

from woob.capabilities.base import NotAvailable, empty
from woob.capabilities.bank import Account
from woob.capabilities.bank.wealth import Investment
from woob.tools.capabilities.bank.transactions import FrenchTransaction
from woob.browser.elements import ItemElement, DictElement, method
from woob.browser.pages import LoggedPage, HTMLPage, JsonPage, XMLPage, RawPage
from woob.browser.filters.standard import (
    CleanText, CleanDecimal, Date,
    Field, MapIn, Eval, Lower,
)
from woob.browser.filters.json import Dict
from woob.tools.capabilities.bank.investments import IsinCode, IsinType


class ConnectionPage(HTMLPage):
    def get_js_link(self):
        # The link to access to the javascript that generates the key changes over time.
        # Nevertheless, we can reconstitute the link from information present in the page.
        get_url_id = re.compile(
            r'\}\[a\]\|\|a\)\+"\.(?P<element>\d*)\."\+\{(.|\n)*,91:"(?P<js_id>\w*)",(.|\n)*\}\[a\]\+"\.chunk\.js";'
        )
        element_id, js_id = get_url_id.search(self.response.text).group('element', 'js_id')
        url = f'https://front-client.intencial.fr/o/main/static/js/91.{element_id}.{js_id}.chunk.js'
        return url

    def get_signature_key(self):
        # To create the signature key, the js uses two arrays present in the script (f and v).
        # For example f = ["00", "68"] and v = ["07", "00"]. These arrays are concatenated and
        # transformed into a string like '00680700...'. This string is cut every 4 elements,
        # (for example '0068'). Each sub-string is converted into a number in base 16. So 0068
        # becomes 104. Finaly this number is then converted in string of character utf16 which
        # gives 'h' and 0700 gives p so in this example the key would be 'hp'.
        get_lists_regex = re.compile(r'f=\[(?P<f>(".{2}",?)*)\],v=\[(?P<v>(".{2}",?)*)\]')
        concat_number_regex = re.compile(r'("|,)')
        js_content = self.browser.open(self.get_js_link())

        matched = get_lists_regex.search(js_content.text)
        assert matched, 'Could not find lists used to forge the JWT signature key for authentication'

        f, v = matched.group('f', 'v')
        complete_chain = f + v
        complete_chain = concat_number_regex.sub('', complete_chain)
        chars = re.findall(r'\w{4}', complete_chain)
        signature_key = ''

        for ngram in chars:
            signature_key += chr(int(ngram, 16))

        assert signature_key, 'Impossible to find the signature key'

        return signature_key


class LoginPage(RawPage):
    def build_doc(self, content):
        if re.compile(r'^<.*>.*</.*>$').match(content.decode()):
            return XMLPage.build_doc(self, self.response.content)
        return JsonPage.build_doc(self, content)

    def get_access_token(self):
        if isinstance(self.doc, dict):
            return Dict('accessToken')(self.doc)
        return CleanText('//accessToken')(self.doc)

    def get_error_message(self):
        if isinstance(self.doc, dict):
            return Dict('message')(self.doc)
        return CleanText('//message')(self.doc)


class InfoPage(LoggedPage, HTMLPage):
    pass


class HomePage(LoggedPage, HTMLPage):
    pass


ACCOUNT_TYPES = {
    'apivie': Account.TYPE_LIFE_INSURANCE,
    'liberalys vie': Account.TYPE_LIFE_INSURANCE,
    'linxea zen': Account.TYPE_LIFE_INSURANCE,
    'frontière efficiente': Account.TYPE_LIFE_INSURANCE,
    'cristalliance vie': Account.TYPE_LIFE_INSURANCE,
    'article 82': Account.TYPE_LIFE_INSURANCE,
    'intencial horizon': Account.TYPE_LIFE_INSURANCE,
    'intencial archipel': Account.TYPE_LIFE_INSURANCE,
    'liberalys retraite': Account.TYPE_PER,
    'perspective génération': Account.TYPE_PER,
    'perp': Account.TYPE_PERP,
    'capi': Account.TYPE_CAPITALISATION,
}


class AccountsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):

        class item(ItemElement):
            klass = Account

            obj_id = obj_number = CleanText(Dict('contratId'))
            obj_label = CleanText(Dict('produit'))
            obj_balance = CleanDecimal.SI(Dict('encours'))
            obj_currency = 'EUR'
            obj_type = MapIn(Lower(Field('label')), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)


class InvestmentPage(LoggedPage, JsonPage):
    @method
    class iter_investments(DictElement):
        item_xpath = 'portefeuille'

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(Dict('libelle'))
            obj_valuation = CleanDecimal.SI(Dict('valorisation'))
            obj_code = IsinCode(CleanText(Dict('code')), default=NotAvailable)
            obj_code_type = IsinType(CleanText(Dict('code')), default=NotAvailable)
            obj_quantity = CleanDecimal.SI(Dict('nombreDeParts', default=None), default=NotAvailable)
            obj_unitvalue = CleanDecimal.SI(Dict('valeurActuelle', default=None), default=NotAvailable)
            obj_unitprice = CleanDecimal.SI(Dict('valeurAchat', default=None), default=NotAvailable)

            def obj_portfolio_share(self):
                share = CleanDecimal.SI(Dict('repartition'), default=NotAvailable)(self)
                if empty(share):
                    return NotAvailable
                return Eval(lambda x: x / 100, share)(self)

            def obj_diff_ratio(self):
                diff_ratio = CleanDecimal.SI(Dict('performance', default=None), default=NotAvailable)(self)
                if empty(diff_ratio):
                    return NotAvailable
                return Eval(lambda x: x / 100, diff_ratio)(self)

            def obj_srri(self):
                srri = CleanDecimal.SI(Dict('risque'), default=NotAvailable)(self)
                if empty(srri) or srri == 0:
                    return NotAvailable
                return int(srri)

    def get_opening_date(self):
        return Date(
            CleanText(Dict('dateEffet')),
            default=NotAvailable
        )(self.doc)


class Transaction(FrenchTransaction):
    pass


class HistoryPage(LoggedPage, JsonPage):
    @method
    class iter_history(DictElement):
        # No item_xpath needed

        class item(ItemElement):
            klass = Transaction

            obj_label = CleanText(Dict('typeMouvement'))
            obj_amount = CleanDecimal.SI(Dict('montantOperation'))
            obj_date = obj_rdate = Date(CleanText(Dict('dateOperation')))
            obj_type = Transaction.TYPE_BANK

            class obj_investments(DictElement):
                item_xpath = 'sousOperations'

                def condition(self):
                    return Dict('sousOperations', default=None)(self)

                class item(ItemElement):
                    klass = Investment

                    obj_label = CleanText(Dict('typeMouvement'))
                    obj_valuation = CleanDecimal.SI(Dict('montantOperation'))
                    obj_vdate = Date(CleanText(Dict('dateOperation')))

            def validate(self, obj):
                # Skip 'Encours' transactions, it is just an information
                # about the current account balance
                return 'Encours' not in obj.label
