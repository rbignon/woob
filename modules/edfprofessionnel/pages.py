# Copyright(C) 2016      Jean Walrave
#
# flake8: compatible
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

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.html import Attr, Link
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    CleanDecimal, CleanText, Coalesce, Date,
    Env, Field, Format, Lower, Regexp,
)
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, RawPage
from woob.capabilities.address import PostalAddress
from woob.capabilities.base import NotAvailable
from woob.capabilities.bill import Bill, Subscription
from woob.capabilities.profile import Person
from woob.tools.json import json


class LoginPage(JsonPage):
    def get_data(self, login, password):
        login_data = self.doc
        login_data['callbacks'][0]['input'][0]['value'] = login
        login_data['callbacks'][1]['input'][0]['value'] = password
        return login_data

    def get_error_message(self):
        return Lower(Dict('callbacks/2/output/0/value', default=''))(self.doc)


class AuthPage(RawPage):
    pass


class ErrorPage(HTMLPage):
    def get_message(self):
        return CleanText('//div[@id="div_text"]/h1 | //div[@id="div_text"]/p')(self.doc)


class BaseRedirectPage(HTMLPage):
    def handle_redirect(self):
        return Regexp(
            Coalesce(
                CleanText('//script[contains(text(), "handleRedirect")]'),
                CleanText('//script[contains(text(), "window.location.replace")]'),
                default=''
            ),
            r"(?:handleRedirect|window\.location\.replace)\('(.*?)'\)",
            default=NotAvailable
        )(self.doc)


class ValidatePage(HTMLPage):
    def handle_redirect(self):
        return Link('//a[contains(@class, "button")]', default=NotAvailable)(self.doc)


class RedirectPage(BaseRedirectPage):
    pass


class AiguillagePage(BaseRedirectPage):
    pass


class MaintenancePage(HTMLPage):
    def get_message(self):
        # Message: "Maintenance en cours"
        return CleanText('//div[@class="infoContent"]/span/text()')(self.doc)


class ClientSpace(BaseRedirectPage):
    def get_aura_config(self):
        aura_config = Regexp(
            CleanText('//script[contains(text(), "token")]'),
            r'auraConfig = (\{.*?\})(;|,\s*cn =.*;)'
        )(self.doc)
        return json.loads(aura_config)


class ClientPremiumSpace(ClientSpace):
    pass


class CnicePage(HTMLPage):
    def get_frontdoor_url(self):
        return Regexp(Attr('//head/meta[@http-equiv="Refresh"]', 'content'), r'URL=(.*)')(self.doc)

    def handle_redirect(self):
        return Regexp(Attr('//head/meta[@http-equiv="Refresh"]', 'content'), r'URL=(.*)')(self.doc)


class AuthenticationErrorPage(HTMLPage):
    def is_here(self):
        return 'problem logging in' in Lower('//h2[@id="header"]')(self.doc)

    def get_error_message(self):
        return CleanText('//div[@id="content"]/form/p')(self.doc)


class AuraPage(LoggedPage, JsonPage):
    # useful tip, when request is malformed this page contains a malformed json (yes i know)
    # and it crash on build_doc, hope that can help you to debug
    def build_doc(self, text):
        doc = super(AuraPage, self).build_doc(text)

        if doc['actions'][0]['id'] == '685;a':  # this is the code when we get documents
            # they are also encoded in json
            value = doc['actions'][1]['returnValue']
            if value is None:
                return {'factures': []}
            return json.loads(value)

        return doc

    def get_subscriber(self):
        return Format(
            "%s %s",
            Dict('actions/0/returnValue/FirstName'),
            Dict('actions/0/returnValue/LastName')
        )(self.doc)

    @method
    class get_profile(ItemElement):
        klass = Person

        obj_firstname = CleanText(Dict('actions/0/returnValue/FirstName'))
        obj_lastname = CleanText(Dict('actions/0/returnValue/LastName'))
        obj_email = CleanText(Dict('actions/0/returnValue/Email'))
        obj_mobile = CleanText(Dict('actions/0/returnValue/MobilePhone'))
        obj_gender = CleanText(Dict('actions/0/returnValue/Salutation'))

    @method
    class fill_profile(ItemElement):
        class obj_postal_address(ItemElement):
            klass = PostalAddress

            obj_full_address = Env('full_address', default=NotAvailable)
            obj_street = Env('street', default=NotAvailable)
            obj_postal_code = Env('postal_code', default=NotAvailable)
            obj_city = Env('city', default=NotAvailable)

            def parse(self, obj):
                full_address = CleanText(Dict('actions/0/returnValue/energyMeters/0/postalAddress'))(self)
                self.env['full_address'] = full_address
                m = re.search(r'(\d{1,4}.*) (\d{5}) (.*)', full_address)
                if m:
                    street, postal_code, city = m.groups()
                    self.env['street'] = street
                    self.env['postal_code'] = postal_code
                    self.env['city'] = city

    @method
    class iter_subscriptions(DictElement):
        item_xpath = 'actions/0/returnValue/energyMeters'

        # here is not a list of subscription, but a list of energy point,
        # and several of them can be related to a same subscription,
        # so yes, we can have duplicate id in this list
        ignore_duplicate = True

        def condition(self):
            # returnValue key contains null instead of a dict when there is no subscription
            return bool(Dict('actions/0/returnValue')(self))

        class item(ItemElement):
            klass = Subscription

            obj_id = CleanText(Dict('contractReference'))
            obj_label = CleanText(Dict('siteName'))
            obj_subscriber = Env('subscriber')
            obj__moe_idpe = CleanText(Dict('ids/epMoeId'))

    @method
    class iter_documents(DictElement):
        item_xpath = 'factures'

        class item(ItemElement):
            klass = Bill

            obj__id = CleanText(Dict('identiteFacture/identifiant'))
            obj_id = Format('%s_%s', Env('subid'), Field('_id'))
            obj_total_price = CleanDecimal.SI(
                Dict('montantFacture/montantTTC', default=NotAvailable),
                default=NotAvailable,
            )
            obj_pre_tax_price = CleanDecimal.SI(
                Dict('montantFacture/montantHT', default=NotAvailable),
                default=NotAvailable,
            )
            obj_vat = CleanDecimal.SI(Dict('taxesFacture/montantTVA', default=NotAvailable), default=NotAvailable)
            obj_date = Date(Dict('caracteristiquesFacture/dateLegaleFacture'), dayfirst=True)
            obj_duedate = Date(Dict('caracteristiquesFacture/dateEcheanceFacture'), dayfirst=True)
            obj_format = 'pdf'

            def obj_label(self):
                return 'Facture du %s' % Field('date')(self).strftime('%d/%m/%Y')

            def obj__message(self):
                # message is needed to download file
                message = {
                    'actions': [
                        {
                            'id': '864;a',
                            'descriptor': 'apex://CNICE_VFC160_ListeFactures/ACTION$getFacturePdfLink',
                            'callingDescriptor': 'markup://c:CNICE_LC232_ListeFactures2',
                            'params': {
                                'factureId': Field('_id')(self),
                            },
                        },
                    ],
                }
                return message

    def get_id_for_download(self):
        return self.doc['actions'][0]['returnValue']


class PdfPage(LoggedPage, RawPage):
    pass
