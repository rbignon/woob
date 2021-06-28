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

from __future__ import unicode_literals

from woob.browser.filters.html import Attr, Link
from woob.browser.pages import JsonPage, HTMLPage, LoggedPage, RawPage
from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.standard import CleanDecimal, CleanText, Regexp, Env, Format, Date, Field, Coalesce
from woob.browser.filters.json import Dict
from woob.capabilities.base import NotAvailable
from woob.capabilities.bill import Subscription, Bill
from woob.tools.json import json


class RedirectClass(HTMLPage):
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


class RedirectPage(RedirectClass):
    pass


class AiguillagePage(RedirectClass):
    pass


class ClientSpace(RedirectClass):
    def get_aura_config(self):
        aura_config = Regexp(CleanText('//script[contains(text(), "token")]'), r'auraConfig = (\{.*?\});')(self.doc)
        return json.loads(aura_config)

    def get_token(self):
        aura_config = self.get_aura_config()
        return aura_config['token']


class ClientPremiumSpace(ClientSpace):
    pass


class CnicePage(HTMLPage):
    def get_frontdoor_url(self):
        return Regexp(Attr('//head/meta[@http-equiv="Refresh"]', 'content'), r'URL=(.*)')(self.doc)


class AuthenticationErrorPage(HTMLPage):
    def is_here(self):
        return CleanText('//h2[@id="header"]')(self.doc) == "Problem Logging In"

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
    class iter_subscriptions(DictElement):
        item_xpath = 'actions/0/returnValue/energyMeters'

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
            obj_total_price = CleanDecimal.SI(Dict('montantFacture/montantTTC', default=NotAvailable), default=NotAvailable)
            obj_pre_tax_price = CleanDecimal.SI(Dict('montantFacture/montantHT', default=NotAvailable), default=NotAvailable)
            obj_vat = CleanDecimal.SI(Dict('taxesFacture/montantTVA', default=NotAvailable), default=NotAvailable)
            obj_date = Date(Dict('caracteristiquesFacture/dateLegaleFacture'), dayfirst=True)
            obj_duedate = Date(Dict('caracteristiquesFacture/dateEcheanceFacture'), dayfirst=True)
            obj_format = 'pdf'

            def obj_label(self):
                return 'Facture du %s' % Field('date')(self).strftime('%d/%m/%Y')

            def obj__message(self):
                # message is needed to download file
                message = {
                    'actions':[
                        {
                            'id': '864;a',
                            'descriptor': 'apex://CNICE_VFC160_ListeFactures/ACTION$getFacturePdfLink',
                            'callingDescriptor': 'markup://c:CNICE_LC232_ListeFactures2',
                            'params': {
                                'factureId': Field('_id')(self)
                            }
                        }
                    ]
                }
                return message

    def get_id_for_download(self):
        return self.doc['actions'][0]['returnValue']


class PdfPage(LoggedPage, RawPage):
    pass
