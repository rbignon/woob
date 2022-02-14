# -*- coding: utf-8 -*-

# Copyright(C) 2018      Vincent A
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

from woob.browser.elements import ListElement, ItemElement, method, TableElement
from woob.browser.filters.html import TableCell, Link, Attr, AbsoluteLink
from woob.browser.filters.standard import (
    CleanText, CleanDecimal, Slugify, Date, Field, Format, Regexp,
)
from woob.browser.pages import HTMLPage, LoggedPage
from woob.capabilities.base import NotAvailable
from woob.capabilities.bank import Account, Transaction
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.profile import Profile
from woob.capabilities.bill import Document, DocumentTypes
from woob.exceptions import (
    BrowserIncorrectPassword, BrowserUnavailable, ActionNeeded,
)
from woob.tools.compat import urljoin


MAIN_ID = '_bolden_'


class MainPage(HTMLPage):
    def check_website_maintenance(self):
        message = CleanText('//h1[contains(text(), "en maintenance")]')(self.doc)
        if message:
            raise BrowserUnavailable(message)


class LoginPage(HTMLPage):
    def do_login(self, username, password):
        form = self.get_form(id='signin-form')
        form['LoginViewModel.Email'] = username
        form['LoginViewModel.Password'] = password
        form.submit()

    def check_error(self):
        # Check wrongpass
        msg = CleanText('//div[has-class("validation-summary-errors")]')(self.doc)
        wrongpass_messages = (
            'Tentative de connexion invalide',
            'Invalid connection attempt',
        )
        if any(msg in message for message in wrongpass_messages):
            raise BrowserIncorrectPassword(msg)

        # Check locked account
        if CleanText('//h1[text()="Locked out."]')(self.doc):
            message = CleanText('//h2[@class="text-danger"]')(self.doc)
            raise ActionNeeded(message)


class OtpPage(HTMLPage):
    def send_otp(self, otp):
        form = self.get_form(xpath='//form[contains(@action, "Verify")]')
        form['Code'] = otp
        form['RememberMe'] = 'true'
        form.submit()

    def get_otp_message(self):
        return CleanText('//div[p[contains(text(), "code de vérification")]]')(self.doc)


class HomeLendPage(LoggedPage, HTMLPage):
    pass


class PortfolioPage(LoggedPage, HTMLPage):
    @method
    class iter_accounts(ListElement):
        class item(ItemElement):
            klass = Account

            obj_id = MAIN_ID
            obj_label = 'Compte Bolden'
            obj_type = Account.TYPE_CROWDLENDING
            obj_currency = 'EUR'
            obj_balance = CleanDecimal.French('//div[p[has-class("investor-state") and contains(text(),"Total compte Bolden :")]]/p[has-class("investor-status")]')
            obj_valuation_diff = CleanDecimal.French('//div[has-class("rent-total")]')

    @method
    class iter_investments(TableElement):
        head_xpath = '//div[@class="tab-wallet"]/table/thead//td'

        col_label = 'Emprunteur'
        col_valuation = 'Capital restant dû'
        col_doc = 'Contrat'
        col_diff = 'Intérêts perçus'

        item_xpath = '//div[@class="tab-wallet"]/table/tbody/tr'

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(TableCell('label'))
            obj_id = Slugify(Field('label'))
            obj_valuation = CleanDecimal(TableCell('valuation'), replace_dots=True)
            obj_diff = CleanDecimal(TableCell('diff'), replace_dots=True, default=NotAvailable)
            obj_code = NotAvailable
            obj_code_type = NotAvailable

            def condition(self):
                # Investments without valuation are expired.
                return CleanDecimal(TableCell('valuation'))(self)

            def obj__docurl(self):
                return urljoin(self.page.url, Link('.//a', default=NotAvailable)(TableCell('doc')(self)[0]))

    def get_liquidity(self):
        return CleanDecimal.French('//div[p[contains(text(), "Fonds disponibles")]]/p[has-class("investor-status")]')(self.doc)


class OperationsPage(LoggedPage, HTMLPage):
    @method
    class iter_history(TableElement):
        head_xpath = '//div[@class="tab-wallet"]/table/thead//td'

        col_date = 'Date'
        col_label = 'Opération'
        col_amount = 'Montant'

        item_xpath = '//div[@class="tab-wallet"]/table/tbody/tr'

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                return not Field('label')(self).startswith('dont ')

            obj_label = CleanText(TableCell('label'))

            def obj_amount(self):
                v = CleanDecimal(TableCell('amount'), replace_dots=True)(self)
                if Field('label')(self).startswith('Investissement'):
                    v = -v
                return v

            obj_date = Date(CleanText(TableCell('date')), dayfirst=True, default=None)


class ProfilePage(LoggedPage, HTMLPage):
    @method
    class get_profile(ItemElement):
        klass = Profile

        obj_name = Format(
            '%s %s',
            Attr('//input[@id="SubModel_FirstName"]', 'value'),
            Attr('//input[@id="SubModel_LastName"]', 'value'),
        )
        obj_phone = Attr('//input[@id="SubModel_Phone"]', 'value')
        obj_address = Format(
            '%s %s %s %s %s',
            Attr('//input[@id="SubModel_Address_Street"]', 'value'),
            Attr('//input[@id="SubModel_Address_Suplement"]', 'value'),
            Attr('//input[@id="SubModel_Address_PostalCode"]', 'value'),
            Attr('//input[@id="SubModel_Address_City"]', 'value'),
            CleanText('//select[@id="SubModel_Address_Country"]/option[@selected]'),
        )

    @method
    class iter_documents(ListElement):
        item_xpath = '//a[starts-with(@href, "/Upload/Show")]'

        class item(ItemElement):
            klass = Document

            obj_label = 'Imprimé fiscal unique'
            obj_type = DocumentTypes.REPORT
            obj_format = 'pdf'

            obj_url = AbsoluteLink('.')
            obj_id = Regexp(Field('url'), r'fileId=(\d+)')
