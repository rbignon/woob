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

from weboob.capabilities.bank import Account, Investment
from weboob.exceptions import BrowserIncorrectPassword
from weboob.browser.pages import LoggedPage
from weboob.browser.selenium import (
    SeleniumPage, VisibleXPath, HasTextCondition, AllCondition, WithinFrame,
    ClickableXPath,
)
from weboob.browser.filters.html import Attr, TableCell
from weboob.browser.filters.standard import (
    CleanText, Regexp, Field, CleanDecimal, Eval,
)
from weboob.browser.elements import method, ListElement, ItemElement, TableElement


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

        el = self.driver.find_element_by_xpath('//input[@id="idBoutonEnrolement"]')
        el.click()


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

            el = self.driver.find_element_by_xpath('//input[@id="submit1"]')
            el.click()


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

            el = self.driver.find_element_by_xpath('//input[@id="submit2"]')
            el.click()


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

            el = self.driver.find_element_by_xpath('//input[@id="submit1"]')
            el.click()


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


class AccountsPage(LoggedPage, DestroyAllAdvertising):
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
                if 'compte titre' in Field('label')(self).lower():
                    return Account.TYPE_MARKET
                return Account.TYPE_UNKNOWN

    @method
    class fill_account(ItemElement):
        obj_balance = CleanDecimal('//table[contains(@class,"compteInventaire")]//tr[td[b[text()="TOTAL"]]]/td[2]', replace_dots=True)


class InvestPage(LoggedPage, DestroyAllAdvertising):
    @method
    class iter_investment(TableElement):
        head_xpath = '//table[contains(@class,"portefeuilleTR")]//tr/th'

        col_label = 'Libellé'
        col_quantity = 'Qté'
        col_unitprice = 'PRU'
        col_unitvalue = 'Cours'
        col_valuation = 'Valo'
        col_diff = '+/- Val.'
        col_portfolio_share = '%'

        item_xpath = '//table[contains(@class,"portefeuilleTR")]//tr[td]'

        class item(ItemElement):
            def condition(self):
                return len(self.el.xpath('./td')) > 5

            klass = Investment

            obj_label = CleanText(TableCell('label'))
            obj_quantity = CleanDecimal(TableCell('quantity'), replace_dots=True)
            obj_unitprice = CleanDecimal(TableCell('unitprice'), replace_dots=True)
            obj_unitvalue = CleanDecimal(TableCell('unitvalue'), replace_dots=True)
            obj_valuation = CleanDecimal(TableCell('valuation'), replace_dots=True)
            obj_diff = CleanDecimal(TableCell('diff'), replace_dots=True)
            obj_portfolio_share = Eval(lambda x: x/100, CleanDecimal(TableCell('portfolio_share'), replace_dots=True))

    @method
    class get_liquidity(ItemElement):
        klass = Investment

        obj_code = 'XX-liquidity'
        obj_code_type = Investment.CODE_TYPE_ISIN
        obj_label = 'Liquidités'
        obj_valuation = CleanDecimal('//td[b[text()="Solde espèces :"]]/following-sibling::td[1]', replace_dots=True)
