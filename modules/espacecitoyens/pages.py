# Copyright(C) 2023      Hugues Mitonneau
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


import re

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import Attr, Link
from woob.browser.filters.standard import CleanDecimal, CleanText, Date, Env, Field, Format, Regexp
from woob.browser.pages import HTMLPage, LoggedPage
from woob.capabilities.bill import Bill, DocumentTypes, Subscription
from woob.tools.date import parse_french_date


class LoginPage(HTMLPage):
    def get_verification_token(self):
        return self.doc.xpath('//input[@name="__RequestVerificationToken"]/@value')

    def login(self, username, password):
        form = self.get_form()
        form['username'] = username
        form['password'] = password
        form['__RequestVerificationToken'] = self.get_verification_token()
        form.submit()

class LoginErrorPage(HTMLPage):
    is_here = '//span[@class="erreurLogin"]'

class HomePage(LoggedPage, HTMLPage):
    @method
    class get_subscriptions(ListElement):
        item_xpath = '//a'
        class item(ItemElement):
            klass = Subscription
            def condition(self):
                return 'href' in self.el.attrib and re.match('.*/FichePersonne/DetailPersonne[?]idDynamic=.*', self.el.attrib['href'])
            obj_id = Regexp(Link('.'), r'.*idDynamic=(\d+).*', '\\1')

class SubscriptionPage(LoggedPage, HTMLPage):
    @method
    class get_subscription(ItemElement):
        klass = Subscription
        obj_id = Env('sub_id')
        obj_label = CleanText('//*[@id="hMonEspaceIdentite"]')

class MyAccountPage(LoggedPage, HTMLPage):
    @method
    class iter_documents(ListElement):
        item_xpath = '//tr[@class="compte"]'
        class item(ItemElement):
            klass = Bill
            obj_id = Attr('.', 'id')
            obj_url = Format('https://www.espace-citoyens.net/%s/espace-citoyens/MonCompte/TelechargerPdfFacture?IdFactureUnique=%s', Env('city'), Field('id'))
            obj_format = "pdf"
            obj_label = CleanText('.//*[@class="ligneCompte"][1]')
            obj_type = DocumentTypes.BILL
            obj_number = CleanText('.//*[@class="numero_facture"]')

class BillingDetailPage(LoggedPage, HTMLPage):
    @method
    class get_document(ItemElement):
        klass = Bill
        obj_id = Env('doc_id')
        obj_url = Format('https://www.espace-citoyens.net/%s/espace-citoyens/MonCompte/TelechargerPdfFacture?IdFactureUnique=%s', Env('city'), Field('id'))
        obj_date = Date(CleanText('.//*[@id="spanDetailFacture_DatEmissionFacture"]'), parse_func=parse_french_date)
        obj_format = "pdf"
        obj_label = CleanText('.//*[@id="hDetailFacture_Facture"]')
        obj_type = DocumentTypes.BILL
        obj_number = Regexp(Field('label'), '.*- (\\d+) -.*', '\\1')
        obj_total_price = CleanDecimal('.//*[@id="spanDetailFacture_MntTotalFacture"]', replace_dots=True)
        obj_currency = "euro"
        obj_duedate = Date(CleanText('.//*[@id="spanDetailFacture_DatLimitePaiementFacture"]'), parse_func=parse_french_date)
