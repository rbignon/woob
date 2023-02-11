# Copyright(C) 2015      Vincent Paredes
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

from woob.browser.elements import ItemElement, ListElement, TableElement, method
from woob.browser.filters.html import Attr, Link, TableCell
from woob.browser.filters.standard import (
    CleanDecimal, CleanText, Currency, Date,
    Field, Format, QueryValue, Regexp,
)
from woob.browser.pages import AbstractPage, HTMLPage, LoggedPage, PartialHTMLPage
from woob.capabilities import NotAvailable
from woob.capabilities.bill import Bill, DocumentTypes, Subscription
from woob.tools.date import parse_french_date


class HiddenFieldPage(HTMLPage):
    def get_ctl00_actScriptManager_HiddenField(self):
        return QueryValue(
            Attr('//script[contains(@src, "js/CombineScriptsHandler.ashx?")]', 'src'),
            "_TSM_CombinedScripts_",
        )(self.doc)


class ProHomePage(LoggedPage, HTMLPage):
    @method
    class get_subscriptions(ListElement):
        item_xpath = '//div[@id="divAccueilInformationClient"]//div[@id="divInformationClient"]'

        class item(ItemElement):
            klass = Subscription

            obj_subscriber = CleanText('.//div[@id="divlblTitleFirstNameLastName"]//span')
            obj_id = CleanText('.//span[2]')
            obj_label = CleanText('.//div[@id="divlblTitleFirstNameLastName"]//span')


class ParLoginPage(AbstractPage):
    PARENT = 'materielnet'
    PARENT_URL = 'login'
    BROWSER_ATTR = 'package.browser.MaterielnetBrowser'

    def login(self, username, password, captcha_response=None):
        form = self.get_form()
        form['Email'] = username
        form['Password'] = password

        # removing this otherwise the login could fail.
        del form['VerificationToken']
        if captcha_response:
            form['g-recaptcha-response'] = captcha_response

        form.submit()


class ProLoginPage(AbstractPage, HiddenFieldPage):
    PARENT = 'materielnet'
    PARENT_URL = 'login'
    BROWSER_ATTR = 'package.browser.MaterielnetBrowser'

    def login(self, username, password, captcha_response=None):
        form = self.get_form(id='aspnetForm', submit='.//input[@id="ctl00_cphMainContent_butConnexion"]')
        form['ctl00_actScriptManager_HiddenField'] = self.get_ctl00_actScriptManager_HiddenField()
        form['ctl00$cphMainContent$txbMail'] = username
        form['ctl00$cphMainContent$txbPassword'] = password

        # remove this, else the login will fail on first try :
        del form['ctl00$SaveCookiesChoices']
        del form['ctl00$btnCookiesNotAccept']
        del form['ctl00$lbCookiesAllAccept']
        if captcha_response:
            form['g-recaptcha-response'] = captcha_response

        form.submit()


class ProfilePage(LoggedPage, HTMLPage):
    @method
    class get_subscriptions(ListElement):
        class Item(ItemElement):
            klass = Subscription

            obj_subscriber = CleanText('//div[@class="hello"]/p/em')
            obj_id = Regexp(CleanText('//span[@class="nclient"]'), r'Nº client : (.*)')
            obj_label = Field('id')


class PeriodPage(AbstractPage):
    PARENT = 'materielnet'
    PARENT_URL = 'periods'
    BROWSER_ATTR = 'package.browser.MaterielnetBrowser'


class ParDocumentsPage(LoggedPage, PartialHTMLPage):
    @method
    class get_documents(ListElement):
        # An order separated in several package will have a lot of
        # dsp-row with no details so the xpath needs to start from order.
        item_xpath = '//div[@class="order"]/div[@class="dsp-table"]/div[@class="dsp-row"]'

        class item(ItemElement):
            klass = Bill

            obj__detail_url = Link('.//a[contains(text(), "Détails")]')
            obj_id = Regexp(CleanText('./div[contains(@class, "cell-nb-order")]'), r'N. (.*)')
            obj_date = Date(CleanText('./div[contains(@class, "cell-date")]'), dayfirst=True)
            obj_format = 'pdf'
            obj_label = Format('Commande N°%s', Field('id'))
            obj_type = DocumentTypes.BILL
            # cents in price will be be separated with € like : 1 234€56
            obj_total_price = CleanDecimal(CleanText('./div[contains(@class, "cell-value")]'), replace_dots=(' ', '€'))
            obj_currency = 'EUR'


class ParDocumentDetailsPage(LoggedPage, PartialHTMLPage):
    @method
    class fill_document(ItemElement):
        klass = Bill

        obj_url = Link('//a[span[contains(text(), "Télécharger la facture")]]', default=NotAvailable)


class ProDocumentsPage(LoggedPage, HiddenFieldPage):
    def get_range(self):
        elements = self.doc.xpath('//select[@id="ctl00_cphMainContent_ddlDate"]/option')
        # theses options can be:
        # * Depuis les (30|60|90) derniers jours
        # * 2020
        # * 2019
        # * etc...
        # we skip those which contains 'derniers jours' because they are also present
        # in the current year and we don't want duplicates.
        for element in elements:
            if 'derniers jours' in CleanText('.')(element):
                continue
            yield Attr('.', 'value')(element)

    def get_view_state(self):
        m = re.search(r'__VIEWSTATE\|(.*?)\|', self.text)
        return m.group(1)

    @method
    class iter_documents(TableElement):
        ignore_duplicate = True
        item_xpath = '//table[@id="TopListing"]/tr[contains(@class, "rowTable")]'
        head_xpath = '//table[@id="TopListing"]/tr[@class="headTable"]/td'

        col_id = 'N° de commande'
        col_date = 'Date'
        col_price = 'Montant HT'
        col_status = 'Statut'

        class item(ItemElement):
            klass = Bill

            def condition(self):
                return CleanText(TableCell('status'))(self) != 'Annulée'

            obj_id = CleanText(TableCell('id'))
            obj_url = '/Account/CommandListingPage.aspx'
            obj_label = Format('Command n°%s', Field('id'))
            obj_format = 'pdf'
            obj_total_price = CleanDecimal.French(TableCell('price'))
            obj_currency = Currency(TableCell('price'))

            def obj_date(self):
                return parse_french_date(CleanText(TableCell('date'))(self)).date()
