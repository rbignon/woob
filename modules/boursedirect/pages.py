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

from weboob.capabilities.base import NotAvailable
from weboob.capabilities.bank import Account, Investment, Transaction
from weboob.exceptions import BrowserIncorrectPassword
from weboob.browser.pages import LoggedPage, HTMLPage, RawPage
from weboob.browser.selenium import (
    SeleniumPage, VisibleXPath, HasTextCondition, AllCondition, WithinFrame,
    ClickableXPath,
)
from weboob.browser.filters.html import Attr, TableCell
from weboob.browser.filters.standard import (
    CleanText, Regexp, Field, CleanDecimal, Date, Eval, Format,
)
from weboob.browser.elements import method, ListElement, ItemElement, TableElement
from selenium.webdriver.common.keys import Keys


class DestroyAllAdvertising(SeleniumPage):
    def remove_by_id(self, id):
        self.driver.execute_script("""
        var el = document.getElementById('%s');
        if (el) {
            el.parentNode.removeChild(el);
        }
        """ % id)

    def on_load(self):
        # dickhead bank site tries to forcefeed you bigger loads of crap ads and banking videos than porn sites

        self.remove_by_id('dfp-videoPop')
        self.remove_by_id('dfp_catFish')
        self.remove_by_id('pub1000x90')

        self.driver.execute_script("""
        var iframes = document.getElementsByTagName('iframe');
        for (var i = 0; i < iframes.length; i++) {
            var el = iframes[i];

            if (el.name == 'google_osd_static_frame' ||
                el.title == '3rd party ad content' ||
                el.id.startsWith('google_ads_iframe_')
            ) {
                el.parentNode.removeChild(el);
            }
        }
        """)


class LoginPage1(DestroyAllAdvertising):
    is_here = VisibleXPath('//input[@id="idLogin"]')

    def on_load(self):
        super(LoginPage1, self).on_load()

        # this toolbar hides the submit button
        self.driver.execute_script("""
        var els = document.getElementsByClassName('header-other');
        for (var i = 0; i < els.length; i++) {
            var el = els[i];

            el.parentNode.removeChild(el);
        }
        """)

    def login(self, username):
        el = self.driver.find_element_by_xpath('//input[@id="idLogin"]')
        el.send_keys(username)
        el.send_keys(Keys.RETURN)


class LoginPageOtp(DestroyAllAdvertising):
    #is_here = VisibleXPath('//div[@id="formstep1"]//span[contains(text(),"Entrez le code reçu par SMS")]')
    is_here = WithinFrame('inwebo', AllCondition(
        ClickableXPath('//input[@id="iw_id"]'),
        ClickableXPath('//input[@id="submit1"]'),
    ))

    def post_otp(self, otp):
        with self.browser.in_frame('inwebo'):
            el = self.driver.find_element_by_xpath('//input[@id="iw_id"]')
            el.click()
            el.send_keys(otp)
            el.send_keys(Keys.RETURN)


class LoginPageProfile(DestroyAllAdvertising):
    is_here = WithinFrame('inwebo', AllCondition(
        ClickableXPath('//input[@id="iw_profile"]'),
        ClickableXPath('//input[@id="iw_pwd_confirm"]'),
        ClickableXPath('//input[@id="submit2"]'),
    ))

    def create_profile(self, profile, password):
        with self.browser.in_frame('inwebo'):
            el = self.driver.find_element_by_xpath('//input[@id="iw_profile"]')
            el.send_keys(profile)

            el = self.driver.find_element_by_xpath('//input[@id="iw_pwd_confirm"]')
            el.send_keys(password)
            el.send_keys(Keys.RETURN)


class LoginPageOk(DestroyAllAdvertising):
    is_here = WithinFrame('inwebo', AllCondition(
        VisibleXPath('//span[@id="LBL_activate_success"]'),
        ClickableXPath('//input[@id="activate_end_action_success"]'),
    ))

    def go_next(self):
        with self.browser.in_frame('inwebo'):
            el = self.driver.find_element_by_xpath('//input[@id="activate_end_action_success"]')
            el.click()


class FinalLoginPage(DestroyAllAdvertising):
    is_here = WithinFrame('inwebo', VisibleXPath('//input[@id="iw_pwd"]'))

    def login(self, username, password):
        with self.browser.in_frame('inwebo'):
            el = self.driver.find_element_by_xpath('//div[@id="iwloginfield"]/input[@id="iw_0"]')
            el.send_keys(username)

            el = self.driver.find_element_by_xpath('//input[@id="iw_pwd"]')
            el.send_keys(password)
            el.send_keys(Keys.RETURN)


class LoginFinalErrorPage(DestroyAllAdvertising):
    is_here = WithinFrame('inwebo', AllCondition(
        VisibleXPath('//input[@id="iw_pwd"]'),
        HasTextCondition('//div[@id="iw_pwderror"]'),
    ))

    def check_error(self):
        with self.browser.in_frame('inwebo'):
            txt = CleanText('//div[@id="iw_pwderror"]')(self.doc)
            assert txt
            raise BrowserIncorrectPassword(txt)


class AccountsPageSelenium(LoggedPage, DestroyAllAdvertising):
    pass


class AccountsPage(HTMLPage):
    @property
    def logged(self):
        return '''function setTop(){top.location="/fr/actualites"}''' not in self.text

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

            if not info[1]:
                continue  # subtotal line or more info ("Vente transmise au marché")

            inv = Investment()
            inv.label = info[0]
            inv.quantity = CleanDecimal(replace_dots=True).filter(info[2])
            inv.unitprice = CleanDecimal(replace_dots=True).filter(info[3])
            inv.unitvalue = CleanDecimal(replace_dots=True).filter(info[4])
            inv.valuation = CleanDecimal(replace_dots=True).filter(info[5])
            inv.diff = CleanDecimal(replace_dots=True).filter(info[6])
            inv.diff_percent = CleanDecimal(replace_dots=True).filter(info[7]) / 100
            inv.portfolio_share = CleanDecimal(replace_dots=True).filter(info[9]) / 100

            yield inv

    def get_liquidity(self):
        parts = self.doc.split('{')

        inv = Investment()
        inv.label = 'Liquidités'
        inv.code = 'XX-Liquidity'
        inv.code_type = Investment.CODE_TYPE_ISIN
        inv.valuation = CleanDecimal(replace_dots=True).filter(parts[3])
        return inv


class LifeInsurancePage(LoggedPage, HTMLPage):
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

    @method
    class iter_history(ListElement):
        class iter_versements(ListElement):
            item_xpath = '//fieldset[legend[text()="Historique des versements"]]/table/tr[@class!="place"]'

            class item(ItemElement):
                klass = Transaction

                obj_date = Date(CleanText('.//td[3]'), dayfirst=True)
                obj_label = Format('Versement %s', CleanText('.//td[4]'))
                obj_amount = CleanDecimal('.//td[6]', replace_dots=True)

        class iter_other(ListElement):
            def parse(self, el):
                texts = [
                    'Historique des arbitrages',
                    'Historique des Rachats partiels',
                    'Historique des demandes d´avance',
                    'Sécurisation des plus values',
                ]
                for text in texts:
                    assert CleanText('.')(self.page.doc.xpath('//fieldset[legend[text()=$text]]/div[@class="noRecord"]', text=text)[0]), '%s is not handled' % text
