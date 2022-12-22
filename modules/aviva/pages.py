# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
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

from urllib.parse import urljoin

from woob.browser.pages import HTMLPage, LoggedPage
from woob.browser.elements import ListElement, ItemElement, method
from woob.browser.filters.standard import (
    CleanText, Format, Date, Regexp, CleanDecimal,
    Currency, Field, Eval, Coalesce, MapIn, Lower, Type,
)
from woob.browser.filters.html import AbsoluteLink, Attr
from woob.capabilities.bank import Account, Transaction
from woob.capabilities.base import empty
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.base import NotAvailable
from woob.exceptions import ActionNeeded, ActionType, BrowserUnavailable
from woob.tools.capabilities.bank.investments import IsinCode, IsinType


class BasePage(HTMLPage):
    def on_load(self):
        super(BasePage, self).on_load()

        if 'Erreur' in CleanText('//div[@id="main"]/h1', default='')(self.doc):
            err = CleanText('//div[@id="main"]/div[@class="content"]', default='Site indisponible')(self.doc)
            raise BrowserUnavailable(err)


class PrevoyancePage(LoggedPage, HTMLPage):
    pass


class LoginPage(BasePage):
    def build_doc(self, content):
        # Useful to Aviva's child (Afer)
        # Some redirects not followed are empty
        if not content:
            content = b'<html></html>'
        return super().build_doc(content)

    def login(self, login, password, allow_redirects=True):
        form = self.get_form(id="loginForm")
        form['username'] = login
        form['password'] = password
        form.submit(allow_redirects=allow_redirects)


class MigrationPage(LoggedPage, HTMLPage):
    def get_error(self):
        return CleanText('//h1[contains(text(), "Votre nouvel identifiant et mot de passe")]')(self.doc)


ACCOUNT_TYPES = {
    "assurance vie": Account.TYPE_LIFE_INSURANCE,
    "retraite madelin": Account.TYPE_MADELIN,
    "article 83": Account.TYPE_ARTICLE_83,
    "plan d'epargne retraite populaire": Account.TYPE_PERP,
    "plan epargne retraite": Account.TYPE_PER,
}


class AccountsPage(LoggedPage, BasePage):
    @method
    class iter_accounts(ListElement):
        item_xpath = '//div[contains(@class, "o-product-roundels")]/div[@data-policy]'

        class item(ItemElement):
            klass = Account

            obj_id = CleanText('./@data-policy')
            obj_number = Field('id')
            obj_label = CleanText('.//p[has-class("a-heading")]', default=NotAvailable)
            obj_url = AbsoluteLink(
                './/a[contains(text(), "Détail") or contains(text(), "Mon adhésion") or contains(text(), "Ma situation")]'
            )

            def condition(self):
                # 'Prévoyance' div is for insurance contracts -- they are not bank accounts and thus are skipped
                ignored_accounts = (
                    'Prévoyance', 'Responsabilité civile', 'Complémentaire santé', 'Protection juridique',
                    'Habitation', 'Automobile',
                )
                return CleanText('../../div[has-class("o-product-tab-category")]', default=NotAvailable)(self) not in ignored_accounts


class InvestmentPage(LoggedPage, HTMLPage):
    @method
    class fill_account(ItemElement):
        obj_balance = Coalesce(
            CleanDecimal.French('//h3[contains(text(), "Valeur de rachat")]/following-sibling::p/strong', default=NotAvailable),
            CleanDecimal.French('//h3[contains(text(), "pargne retraite")]/following-sibling::p/strong', default=NotAvailable),
            CleanDecimal.French('//h3[contains(text(), "Capital constitutif de rente")]/following-sibling::p', default=NotAvailable),
            CleanDecimal.French('//h2[contains(text(), "pargne constituée")]/span', default=NotAvailable),
            CleanDecimal.French('//h2[contains(text(), "pargne disponible")]/span', default=NotAvailable),
            # Afer xpaths
            CleanDecimal.French('//h2[contains(text(), "Valeur de rachat")]/span', default=NotAvailable),
            CleanDecimal.French('//h2[contains(text(), "pargne retraite")]/span', default=NotAvailable),
            CleanDecimal.French('//h2[contains(text(), "Capital constitutif de rente")]/span', default=NotAvailable),
        )
        obj_currency = Coalesce(
            # Aviva xpaths
            Currency('//h3[contains(text(), "Valeur de rachat")]/following-sibling::p/strong', default=NotAvailable),
            Currency('//h3[contains(text(), "pargne retraite")]/following-sibling::p/strong', default=NotAvailable),
            Currency('//h3[contains(text(), "Capital constitutif de rente")]/following-sibling::p', default=NotAvailable),
            Currency('//h2[contains(text(), "pargne constituée")]/span', default=NotAvailable),
            Currency('//h2[contains(text(), "pargne disponible")]/span', default=NotAvailable),
            # Afer xpaths
            Currency('//h2[contains(text(), "Valeur de rachat")]/span', default=NotAvailable),
            Currency('//h2[contains(text(), "pargne retraite")]/span', default=NotAvailable),
            Currency('//h2[contains(text(), "Capital constitutif de rente")]/span', default=NotAvailable),
        )
        obj_valuation_diff = CleanDecimal.French('//h3[contains(., "value latente")]/following-sibling::p[1]', default=NotAvailable)
        obj_type = MapIn(Lower(CleanText('//h3[contains(text(), "Type de produit")]/following-sibling::p')), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)
        # Opening date titles may have slightly different names and apostrophe characters
        obj_opening_date = Coalesce(
            Date(CleanText('''//h3[contains(text(), "Date d'effet de l'adhésion")]/following-sibling::p'''), dayfirst=True, default=NotAvailable),
            Date(CleanText('''//h3[contains(text(), "Date d’effet d’adhésion")]/following-sibling::p'''), dayfirst=True, default=NotAvailable),
            Date(CleanText('''//h3[contains(text(), "Date d’effet fiscale")]/following-sibling::p'''), dayfirst=True, default=NotAvailable),
            default=NotAvailable
        )

    def get_history_link(self):
        history_link = self.doc.xpath('//li/a[contains(text(), "Historique")]/@href')
        return urljoin(self.browser.BASEURL, history_link[0]) if history_link else ''

    def unavailable_details(self):
        return CleanText(
            '//p[contains(text(), "est pas disponible") or contains(text(), "est pas possible")]'
        )(self.doc)

    def is_valuation_available(self):
        return (
            # Aviva balance xpaths
            self.doc.xpath('//h3[contains(text(), "Valeur de rachat")]/following-sibling::p/strong') or
            self.doc.xpath('//h3[contains(text(), "pargne retraite")]/following-sibling::p/strong') or
            self.doc.xpath('//h3[contains(text(), "Capital constitutif de rente")]/following-sibling::p') or
            self.doc.xpath('//h2[contains(text(), "pargne constituée")]/span') or
            self.doc.xpath('//h2[contains(text(), "pargne disponible")]/span') or
            # Afer balance xpaths
            self.doc.xpath('//h2[contains(text(), "Valeur de rachat")]/span') or
            self.doc.xpath('//h2[contains(text(), "pargne retraite")]/span') or
            self.doc.xpath('//h2[contains(text(), "Capital constitutif de rente")]/span')
        )

    @method
    class iter_investment(ListElement):
        # Specify "count(td) > 3" to skip lines from the "Tableau de Répartition" (only contains percentages)
        item_xpath = '//div[contains(@class, "m-table")]//table[.//th[contains(.,"Valeur de la part")]]/tbody/tr[not(contains(@class, "total")) and count(td) > 3]'

        class item(ItemElement):
            klass = Investment

            def condition(self):
                return Field('label')(self) not in ('Total', '')

            obj_quantity = CleanDecimal.French(
                './td[contains(@data-label, "Nombre de parts") or contains(@data-th, "Nombre de parts")]',
                default=NotAvailable
            )

            obj_unitvalue = CleanDecimal.French(
                './td[contains(@data-label, "Valeur de la part") or contains(@data-th, "Valeur de la part")]',
                default=NotAvailable
            )

            def obj_unitprice(self):
                # initial valuation divided by the quantity to have the unitprice.
                invested = CleanDecimal.French('./td[contains(@data-th, "Prime investie")]', default=NotAvailable)(self)
                quantity = Field('quantity')(self)
                if not empty(invested) and quantity:
                    return round(invested / quantity, 2)
                return NotAvailable

            obj_valuation = Coalesce(
                CleanDecimal.French('./td[contains(@data-label, "Valeur de rachat")]', default=NotAvailable),
                CleanDecimal.French(CleanText('./td[contains(@data-label, "Montant")]', children=False), default=NotAvailable),
                CleanDecimal.French(CleanText('./td[contains(@data-th, "Montant")]'), default=NotAvailable),
            )

            def obj_portfolio_share(self):
                share = CleanDecimal.French('./td[contains(@data-th, "%")]', default=NotAvailable)(self)
                if not empty(share):
                    return share / 100
                return NotAvailable

            obj_vdate = Date(
                CleanText('./td[@data-label="Date de valeur" or @data-th="Date de valeur"]'), dayfirst=True, default=NotAvailable
            )

            # XPath is "Nom du support" most of the time but can be "Nom du su" for some connections
            obj_label = Coalesce(
                CleanText('./th[contains(@data-label, "Nom du su")]/a'),
                CleanText('./th[contains(@data-label, "Nom du su")]'),
                CleanText('./td[contains(@data-label, "Nom du su")]'),
                CleanText('./th[1]'),
            )

            # Note: ISIN codes are not available on the 'afer' website
            obj_code = IsinCode(
                Regexp(
                    CleanText('./th[1]/a/@onclick'),
                    r'"(.*)"',
                    default=NotAvailable
                ),
                default=NotAvailable
            )
            obj_code_type = IsinType(Field('code'))


class HistoryPage(LoggedPage, HTMLPage):
    @method
    class iter_versements(ListElement):
        item_xpath = '//div[contains(@id, "versementProgramme3") or contains(@id, "versementLibre3")]/h2'

        class item(ItemElement):
            klass = Transaction

            obj_date = Date(
                Regexp(CleanText('./div[1]'), r'(\d{2}\/\d{2}\/\d{4})'),
                dayfirst=True
            )
            obj_amount = Eval(lambda x: x / 100, CleanDecimal('./div[2]'))
            obj_label = Format(
                '%s %s',
                CleanText('./preceding::h3[1]'),
                Regexp(CleanText('./div[1]'), r'(\d{2}\/\d{2}\/\d{4})')
            )

            def obj_investments(self):
                investments = []

                for elem in self.xpath('./following-sibling::div[1]//ul'):
                    inv = Investment()
                    inv.label = CleanText('./li[1]/p')(elem)
                    inv.portfolio_share = CleanDecimal('./li[2]/p', replace_dots=True, default=NotAvailable)(elem)
                    inv.quantity = CleanDecimal('./li[3]/p', replace_dots=True, default=NotAvailable)(elem)
                    inv.valuation = CleanDecimal('./li[4]/p', replace_dots=True)(elem)
                    investments.append(inv)

                return investments

    @method
    class iter_arbitrages(ListElement):
        item_xpath = '//div[contains(@id, "arbitrageLibre3")]/h2'

        class item(ItemElement):
            klass = Transaction

            obj_date = Date(
                Regexp(CleanText('.//div[1]'), r'(\d{2}\/\d{2}\/\d{4})'),
                dayfirst=True
            )
            obj_label = Format(
                '%s %s',
                CleanText('./preceding::h3[1]'),
                Regexp(CleanText('./div[1]'), r'(\d{2}\/\d{2}\/\d{4})')
            )

            def obj_amount(self):
                return sum(x.valuation for x in Field('investments')(self))

            def obj_investments(self):
                investments = []
                for elem in self.xpath('./following-sibling::div[1]//tbody/tr'):
                    inv = Investment()
                    inv.label = CleanText('./td[1]')(elem)
                    inv.valuation = Coalesce(
                        CleanDecimal.French('./td[2]/p', default=NotAvailable),
                        CleanDecimal.French('./td[2]')
                    )(elem)
                    investments.append(inv)

                return investments


class ActionNeededPage(LoggedPage, HTMLPage):
    def on_load(self):
        raise ActionNeeded(
            locale="fr-FR", message="Veuillez mettre à jour vos coordonnées",
            action_type=ActionType.FILL_KYC,
        )


class ValidationPage(LoggedPage, HTMLPage):
    def on_load(self):
        error_message = CleanText('//p[@id="errorSigned"]')(self.doc)
        if error_message:
            raise ActionNeeded(error_message)


class InvestDetailPage(LoggedPage, HTMLPage):
    def is_empty(self):
        return not self.doc.xpath('//table')


class InvestPerformancePage(LoggedPage, HTMLPage):
    @method
    class fill_investment(ItemElement):
        obj_srri = Type(
            Regexp(
                Attr(
                    '//span[contains(@class, "icon-risk")]', 'class'
                ),
                r'.*-(\d)',
                default=''
            ),
            type=int,
            default=NotAvailable
        )
        obj_description = obj_asset_category = CleanText('//td[contains(text(), "Nature")]/following-sibling::td')


class MaintenancePage(HTMLPage):
    pass
