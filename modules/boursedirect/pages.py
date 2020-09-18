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

# flake8: compatible

from __future__ import unicode_literals

import re

from weboob.capabilities.base import NotAvailable
from weboob.capabilities.bank import Account, Transaction
from weboob.capabilities.wealth import (
    Investment, MarketOrder, MarketOrderDirection,
    MarketOrderType, MarketOrderPayment,
)
from weboob.exceptions import (
    BrowserIncorrectPassword, BrowserPasswordExpired, ActionNeeded,
    BrowserHTTPNotFound, BrowserUnavailable,
)
from weboob.browser.pages import HTMLPage, RawPage
from weboob.browser.filters.html import Attr, TableCell, ReplaceEntities
from weboob.browser.filters.standard import (
    CleanText, Currency, Regexp, Field, CleanDecimal,
    Date, Eval, Format, MapIn, Base, Lower, QueryValue,
)
from weboob.browser.filters.html import Link
from weboob.browser.elements import method, ListElement, ItemElement, TableElement
from weboob.tools.capabilities.bank.investments import (
    is_isin_valid, create_french_liquidity, IsinCode, IsinType,
)


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

        if "Erreur d'authentification" in msg:
            raise BrowserUnavailable(msg)

        if "votre compte a été bloqué" in msg:
            raise ActionNeeded(msg)

        if msg:
            raise AssertionError('There seems to be an unhandled error message: %s' % msg)


class PasswordRenewalPage(HTMLPage):
    def get_message(self):
        return CleanText('//p[@class="auth-intro"]')(self.doc)


class BasePage(HTMLPage):
    @property
    def logged(self):
        return (
            '''function setTop(){top.location="/fr/actualites"}''' not in self.text
            or CleanText('//body')(self.doc)
        )


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
        obj_balance = CleanDecimal.French('//table[contains(@class,"compteInventaire")]//tr[td[b[text()="TOTAL"]]]/td[2]')


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
                    inv.valuation = CleanDecimal.French().filter(info[6])
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

            inv.quantity = CleanDecimal.French().filter(info[2])

            inv.original_currency = Currency().filter(info[4])
            # info[4] = '123,45 &euro;' for investments made in euro, so this filter will return None
            if inv.original_currency:
                inv.original_unitvalue = CleanDecimal.French().filter(info[4])
            else:
                # info[4] may be empty so we must handle the default value
                inv.unitvalue = CleanDecimal.French(default=NotAvailable).filter(info[4])

            inv.unitprice = CleanDecimal.French().filter(info[3])
            inv.diff = CleanDecimal.French().filter(info[6])
            inv.diff_ratio = CleanDecimal.French().filter(info[7]) / 100
            if info[9]:
                # portfolio_share value may be empty
                inv.portfolio_share = CleanDecimal.French().filter(info[9]) / 100
            inv.code = self.get_isin(info)
            inv.code_type = IsinType(default=NotAvailable).filter(inv.code)

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
                try:
                    isin_page = self.browser.open(url).page
                except BrowserHTTPNotFound:
                    # Sometimes the 301 redirection leads to a 404
                    return code
                # Checking that we were correctly redirected:
                if hasattr(isin_page, 'next_url'):
                    isin_page = self.browser.open(isin_page.next_url()).page

                if "/fr/marche/" in isin_page.url:
                    isin = isin_page.get_isin()
                    if is_isin_valid(isin):
                        code = isin
        return code

    def get_liquidity(self):
        parts = self.doc.split('{')
        valuation = CleanDecimal.French().filter(parts[3])
        return create_french_liquidity(valuation)


class JsRedirectPage(HTMLPage):
    def next_url(self):
        return re.search(r'window.top.location.href = "([^"]+)"', self.text).group(1)


MARKET_ORDER_DIRECTIONS = {
    'Achat': MarketOrderDirection.BUY,
    'Vente': MarketOrderDirection.SALE,
}

MARKET_ORDER_TYPES = {
    'au marché': MarketOrderType.MARKET,
    'cours limité': MarketOrderType.LIMIT,
    'seuil de declcht': MarketOrderType.TRIGGER,
    'plage de declcht': MarketOrderType.TRIGGER,
}

MARKET_ORDER_PAYMENTS = {
    'Cpt': MarketOrderPayment.CASH,
    'SRD': MarketOrderPayment.DEFERRED,
}


class MarketOrdersPage(BasePage):
    ENCODING = 'iso-8859-1'

    @method
    class iter_market_orders(TableElement):
        head_xpath = '//div[div[h6[text()="Ordres en carnet"]]]//table//th'
        item_xpath = '//div[div[h6[text()="Ordres en carnet"]]]//table//tr[position()>1]'
        # <div> is for boursedirect, <td> is for ing
        empty_xpath = '//div|td[text()="Pas d\'ordre pour ce compte"]'

        col_direction = 'Sens'
        col_label = 'Valeur'
        col_quantity = 'Quantité'
        col_ordervalue = 'Limite'
        col_state = 'Etat'
        col_unitvalue = 'Cours Exec'
        col_validity_date = 'Validité'
        col_url = 'Détail'

        class item(ItemElement):
            klass = MarketOrder

            # Extract the ID from the URL (for example detailOrdre.php?cn=<account_id>&ref=<order_id>&...)
            obj_id = QueryValue(Base(TableCell('url'), Link('.//a', default=NotAvailable)), 'ref', default=NotAvailable)
            obj_label = CleanText(TableCell('label'))
            # Catch everything until "( )"
            obj_state = Regexp(
                CleanText(TableCell('state')),
                r'(.*?)(?: \(|$)',
                default=NotAvailable
            )
            obj_quantity = Eval(abs, CleanDecimal.French(TableCell('quantity')))
            obj_ordervalue = CleanDecimal.French(TableCell('ordervalue'), default=NotAvailable)
            obj_unitvalue = CleanDecimal.French(TableCell('unitvalue'), default=NotAvailable)
            obj_validity_date = Date(CleanText(TableCell('validity_date')), dayfirst=True)
            obj_direction = MapIn(
                CleanText(TableCell('direction')),
                MARKET_ORDER_DIRECTIONS,
                MarketOrderDirection.UNKNOWN
            )
            obj_url = Regexp(
                Base(TableCell('url'), Link('.//a', default=NotAvailable)),
                r"ouvrePopup\('([^']+)",
                default=NotAvailable
            )
            # State column also contains stock_market & payment_method (e.g. "(Cpt NYX)")
            obj_stock_market = Regexp(
                CleanText(TableCell('state')),
                r'\((?:Cpt|SRD) (.*)\)',
                default=NotAvailable
            )
            obj_payment_method = MapIn(
                Regexp(
                    CleanText(TableCell('state')),
                    r'\((.*)\)',
                    default=''
                ),
                MARKET_ORDER_PAYMENTS,
                MarketOrderPayment.UNKNOWN
            )


class MarketOrderDetailsPage(BasePage):
    ENCODING = 'iso-8859-1'

    @method
    class fill_market_order(ItemElement):
        obj_date = Date(
            CleanText('//td[text()="Création"]/following-sibling::td[1]'),
            dayfirst=True,
            default=NotAvailable
        )
        obj_execution_date = Date(
            CleanText('//td[text()="Date exécuté"]/following-sibling::td[1]'),
            dayfirst=True,
            default=NotAvailable
        )
        obj_order_type = MapIn(
            Lower(CleanText('//td[text()="Limite"]/following-sibling::td[1]')),
            MARKET_ORDER_TYPES,
            MarketOrderType.UNKNOWN
        )

        obj_code = IsinCode(
            Regexp(
                CleanText('//td[text()="Valeur"]/following-sibling::td[1]'),
                r"\(([^)]+)",
                default=NotAvailable
            ),
            default=NotAvailable
        )


class HistoryPage(BasePage):
    @method
    class iter_history(ListElement):
        item_xpath = '//table[@class="datas retour"]//tr[@class="row1" or @class="row2"]'

        class item(ItemElement):
            klass = Transaction

            obj_date = Date(CleanText('./td[2]'), dayfirst=True)  # Date affectation
            obj_rdate = Date(CleanText('./td[1]'), dayfirst=True)  # Date opération
            obj_label = Format('%s - %s', CleanText('./td[3]/a'), CleanText('./td[4]'))
            obj_amount = CleanDecimal.French('./td[7]')


class IsinPage(HTMLPage):
    def get_isin(self):
        # For american funds, the ISIN code is hidden somewhere else in the page:
        return (
            CleanText('//div[@class="instrument-isin"]/span')(self.doc)
            or Regexp(
                CleanText('//div[contains(@class, "visible-lg")]//a[contains(@href, "?isin=")]/@href'),
                r'isin=([^&]+)'
            )(self.doc)
        )


class LifeInsurancePage(BasePage):
    def has_account(self):
        message = CleanText('//fieldset[legend[text()="Message"]]')(self.doc)
        if 'Vous n´avez pas de contrat. Ce service ne vous est pas accessible.' in message:
            return False
        return True

    @method
    class get_account(ItemElement):
        klass = Account

        obj_balance = CleanDecimal.French('''//label[text()="Valorisation de l'encours"]/following-sibling::b[1]''')
        obj_currency = 'EUR'
        obj_id = obj_number = CleanText('''//label[text()="N° d'adhésion"]/following-sibling::b[1]''')
        obj_label = Format(
            '%s (%s)',
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
            obj_quantity = CleanDecimal.French(TableCell('quantity'), default=NotAvailable)
            obj_unitprice = CleanDecimal.French(TableCell('unitprice'), default=NotAvailable)
            obj_valuation = CleanDecimal.French(TableCell('valuation'), default=NotAvailable)
            obj_vdate = Date(CleanText(TableCell('vdate')), dayfirst=True)
            obj_portfolio_share = Eval(lambda x: x / 100, CleanDecimal.French(TableCell('portfolio_share')))

            def obj_code(self):
                # 'href', 'alt' & 'title' attributes all contain the ISIN
                isin = Attr(TableCell('label')(self)[0], 'title', default=NotAvailable)(self)
                return IsinCode(default=NotAvailable).filter(isin)

            obj_code_type = IsinType(Field('code'), default=NotAvailable)

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
                    assert CleanText('.')(self.page.doc.xpath(
                        '//fieldset[legend[text()=$text]]//div[@class="noRecord"]',
                        text=text,
                    )[0]), '%s is not handled' % text


class PortfolioPage(BasePage):
    # we don't do anything here, but we might land here from a SSO like ing
    pass
