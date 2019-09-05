# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
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

from weboob.capabilities.base import NotAvailable
from weboob.capabilities.bank import Account, Investment, Transaction
from weboob.exceptions import BrowserIncorrectPassword, BrowserPasswordExpired, ActionNeeded
from weboob.browser.pages import HTMLPage, RawPage
from weboob.browser.filters.html import Attr, TableCell, ReplaceEntities
from weboob.browser.filters.standard import (
    CleanText, Regexp, Field, CleanDecimal, Date, Eval, Format,
)
from weboob.browser.elements import method, ListElement, ItemElement, TableElement
from weboob.tools.capabilities.bank.investments import is_isin_valid, create_french_liquidity


class LoginPage(HTMLPage):
    def do_login(self, username, password):
        form = self.get_form(id='authentication')
        form['bd_auth_login_type[login]'] = username
        form['bd_auth_login_type[password]'] = password
        form.submit()

    def check_error(self):
        msg = CleanText('//div[@class="auth-alert-message"]')(self.doc)

        if "votre mot de passe doit être réinitialisé" in msg:
            raise BrowserPasswordExpired()

        if "Couple login mot de passe incorrect" in msg:
            raise BrowserIncorrectPassword()

        if "votre compte a été bloqué" in msg:
            raise ActionNeeded(msg)

        assert not msg, 'there seems to be an unhandled error message'


class BasePage(HTMLPage):
    @property
    def logged(self):
        return ('''function setTop(){top.location="/fr/actualites"}''' not in self.text or CleanText('//body')(self.doc))


class AccountsPage(BasePage):
    @method
    class iter_accounts(ListElement):
        item_xpath = '//select[@id="nc"]/option'

        class item(ItemElement):
            klass = Account

            text = CleanText('.')

            obj_id = obj_number = Regexp(text, r'^(\w+)')
            obj_label = Regexp(text, r'^\w+ (.*)')
            obj_currency = 'EUR'
            obj__select = Attr('.', 'value')

            def obj_type(self):
                label = Field('label')(self).lower()
                if 'compte titre' in label:
                    return Account.TYPE_MARKET
                elif 'pea' in label:
                    return Account.TYPE_PEA
                return Account.TYPE_UNKNOWN

    @method
    class fill_account(ItemElement):
        obj_balance = CleanDecimal('//table[contains(@class,"compteInventaire")]//tr[td[b[text()="TOTAL"]]]/td[2]', replace_dots=True)


class InvestPage(RawPage):
    def build_doc(self, content):
        return content.decode('latin-1')

    @property
    def logged(self):
        # if it's html, then we're not logged
        return not self.doc.lstrip().startswith('<')

    def iter_investment(self):
        assert self.doc.startswith('message=')

        invests = self.doc.split('|')[1:]

        for part in invests:
            if part == '1':
                continue  # separator line

            info = part.split('#')
            if 'Vente transmise au marché' in info:
                # invest sold or not available yet
                continue

            if info[2] == '&nbsp;':
                # space info[2]: not possessed yet, buy is pending
                # "Achat en liq" means that user is using SRD
                if "Achat en liq" in info[0]:
                    inv = Investment()

                    inv.label = "SRD %s" % self.last_name
                    inv.valuation = CleanDecimal(replace_dots=True).filter(info[6])
                    inv.code = self.last_code
                    yield inv

                self.last_name, self.last_code = info[0], self.get_isin(info)
                continue

            inv = Investment()

            inv.label = info[0]

            # Skip investments that have no valuation yet
            inv.valuation = CleanDecimal.French(default=NotAvailable).filter(info[5])
            if inv.valuation == NotAvailable:
                continue

            inv.quantity = CleanDecimal(replace_dots=True).filter(info[2])
            inv.unitprice = CleanDecimal(replace_dots=True).filter(info[3])
            inv.unitvalue = CleanDecimal(replace_dots=True).filter(info[4])
            inv.diff = CleanDecimal(replace_dots=True).filter(info[6])
            inv.diff_ratio = CleanDecimal(replace_dots=True).filter(info[7]) / 100
            inv.portfolio_share = CleanDecimal(replace_dots=True).filter(info[9]) / 100
            inv.code = self.get_isin(info)
            inv.code_type = Investment.CODE_TYPE_ISIN if inv.code else NotAvailable

            self.last_name, self.last_code = inv.label, inv.code
            yield inv

    def get_isin(self, info):
        raw = ReplaceEntities().filter(info[1])
        # Sometimes the ISIN code is already available in the info:
        val = re.search(r'val=([^&]+)', raw)
        code = NotAvailable
        if val and "val=" in raw and is_isin_valid(val.group(1)):
            code = val.group(1)
        else:
            # Otherwise we need another request to get the ISIN:
            m = re.search(r'php([^{]+)', raw)
            if m:
                url = "/priv/fiche-valeur.php" + m.group(1)
                isin_page = self.browser.open(url).page
                # Checking that we were correctly redirected:
                if "/fr/marche/" in isin_page.url:
                    isin = isin_page.get_isin()
                    if is_isin_valid(isin):
                        code = isin
        return code

    def get_liquidity(self):
        parts = self.doc.split('{')
        valuation = CleanDecimal(replace_dots=True).filter(parts[3])
        return create_french_liquidity(valuation)


class HistoryPage(BasePage):
    @method
    class iter_history(ListElement):
        item_xpath = '//table[@class="datas retour"]//tr[@class="row1" or @class="row2"]'

        class item(ItemElement):
            klass = Transaction

            obj_date = Date(CleanText('./td[2]'), dayfirst=True)  # Date affectation
            obj_rdate = Date(CleanText('./td[1]'), dayfirst=True)  # Date opération
            obj_label = Format('%s - %s', CleanText('./td[3]/a'), CleanText('./td[4]'))
            obj_amount = CleanDecimal('./td[7]', replace_dots=True)


class IsinPage(HTMLPage):
    def get_isin(self):
        # For american funds, the ISIN code is hidden somewhere else in the page:
        return CleanText('//div[@class="instrument-isin"]/span')(self.doc) \
            or Regexp(CleanText('//div[contains(@class, "visible-lg")]//a[contains(@href, "?isin=")]/@href'), r'isin=([^&]+)')(self.doc)


class LifeInsurancePage(BasePage):
    def has_account(self):
        message = CleanText('//fieldset[legend[text()="Message"]]')(self.doc)
        if 'Vous n´avez pas de contrat. Ce service ne vous est pas accessible.' in message:
            return False
        return True

    @method
    class get_account(ItemElement):
        klass = Account

        obj_balance = CleanDecimal('''//label[text()="Valorisation de l'encours"]/following-sibling::b[1]''', replace_dots=True)
        obj_currency = 'EUR'
        obj_id = obj_number = CleanText('''//label[text()="N° d'adhésion"]/following-sibling::b[1]''')
        obj_label = Format('%s (%s)',
            CleanText('//label[text()="Nom"]/following-sibling::b[1]'),
            CleanText('//label[text()="Produit"]/following-sibling::b[1]'),
        )
        obj_type = Account.TYPE_LIFE_INSURANCE

    @method
    class iter_investment(TableElement):
        head_xpath = '//fieldset[legend[text()="Répartition de l´encours"]]/table/tr[@class="place"]/th'
        item_xpath = '//fieldset[legend[text()="Répartition de l´encours"]]/table/tr[@class!="place"]'

        col_label = 'Nom des supports'
        col_quantity = 'Nombre de parts'
        col_unitprice = 'Prix Moyen d´Achat'
        col_valuation = 'Valorisation des supports'
        col_vdate = 'Date de valorisation'
        col_portfolio_share = '(%)'

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(TableCell('label'))
            obj_quantity = CleanDecimal(TableCell('quantity'), default=NotAvailable, replace_dots=True)
            obj_unitprice = CleanDecimal(TableCell('unitprice'), default=NotAvailable, replace_dots=True)
            obj_valuation = CleanDecimal(TableCell('valuation'), default=NotAvailable, replace_dots=True)
            obj_vdate = Date(CleanText(TableCell('vdate')), dayfirst=True)
            obj_portfolio_share = Eval(lambda x: x / 100, CleanDecimal(TableCell('portfolio_share'), replace_dots=True))

            def obj_code(self):
                # 'href', 'alt' & 'title' attributes all contain the ISIN
                isin = Attr(TableCell('label')(self)[0], 'title', default=NotAvailable)(self)
                return isin if is_isin_valid(isin) else NotAvailable

            def obj_code_type(self):
                return Investment.CODE_TYPE_ISIN if Field('code')(self) != NotAvailable else NotAvailable

    @method
    class iter_history(ListElement):
        # Historique des versements:
        class iter_versements(ListElement):
            item_xpath = '//fieldset[legend[text()="Historique des versements"]]/table/tr[@class!="place"]'

            class item(ItemElement):
                klass = Transaction

                obj_date = Date(CleanText('.//td[3]'), dayfirst=True)
                obj_label = Format('Versement %s', CleanText('.//td[4]'))
                obj_amount = CleanDecimal.French('.//td[6]')

        # Historique des Rachats partiels:
        class iter_partial_repurchase(ListElement):
            item_xpath = '//fieldset[legend[text()="Historique des Rachats partiels"]]/table/tr[@class!="place"]'

            class item(ItemElement):
                klass = Transaction

                obj_date = Date(CleanText('.//td[3]'), dayfirst=True)
                obj_label = Format('Rachat %s', CleanText('.//td[4]'))
                obj_amount = CleanDecimal.French('.//td[5]')

        # Historique des demandes d´avance:
        class iter_advances(ListElement):
            item_xpath = '//fieldset[legend[text()="Historique des demandes d´avance"]]/table/tr[@class!="place"]'

            class item(ItemElement):
                klass = Transaction

                obj_date = Date(CleanText('.//td[3]'), dayfirst=True)
                obj_label = Format('Demande d\'avance %s', CleanText('.//td[4]'))
                obj_amount = CleanDecimal.French('.//td[5]')

        '''
        - We do not fetch the "Historique des arbitrages" category
          because the transactions have no available amount.
        - The part below will crash if the remaining table is not empty:
          it will be the occasion to implement the scraping of these transactions.
        '''
        class iter_other(ListElement):
            def parse(self, el):
                texts = [
                    'Sécurisation des plus values',
                ]
                for text in texts:
                    assert CleanText('.')(self.page.doc.xpath('//fieldset[legend[text()=$text]]//div[@class="noRecord"]', text=text)[0]), '%s is not handled' % text
