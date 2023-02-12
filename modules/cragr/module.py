# -*- coding: utf-8 -*-

# Copyright(C) 2012-2019  Budget Insight
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

from datetime import date
from collections import OrderedDict

from woob.tools.value import Value, ValueBackendPassword
from woob.tools.backend import BackendConfig, Module
from woob.capabilities.base import find_object
from woob.tools.capabilities.bank.iban import is_iban_valid
from woob.capabilities.bill import (
    CapDocument, Subscription, Document, DocumentNotFound, DocumentTypes,
)
from woob.capabilities.profile import CapProfile
from woob.capabilities.bank import (
    CapBankTransferAddRecipient, Account, AccountNotFound,
)
from woob.capabilities.bank.wealth import CapBankWealth

from .browser import CreditAgricoleBrowser

__all__ = ['CreditAgricoleModule']


class CreditAgricoleModule(Module, CapBankWealth, CapDocument, CapBankTransferAddRecipient, CapProfile):
    NAME = 'cragr'
    MAINTAINER = 'Quentin Defenouillère'
    EMAIL = 'quentin.defenouillere@budget-insight.com'
    VERSION = '3.3.1'
    DEPENDENCIES = ('netfinca',)
    DESCRIPTION = 'Crédit Agricole'
    LICENSE = 'LGPLv3+'

    region_choices = {
        'www.ca-alpesprovence.fr': 'Alpes Provence',
        'www.ca-alsace-vosges.fr': 'Alsace-Vosges',
        'www.ca-anjou-maine.fr': 'Anjou Maine',
        'www.ca-aquitaine.fr': 'Aquitaine',
        'www.ca-atlantique-vendee.fr': 'Atlantique Vendée',
        'www.ca-briepicardie.fr': 'Brie Picardie',
        'www.ca-cb.fr': 'Champagne Bourgogne',
        'www.ca-centrefrance.fr': 'Centre France',
        'www.ca-centreloire.fr': 'Centre Loire',
        'www.ca-centreouest.fr': 'Centre Ouest',
        'www.ca-centrest.fr': 'Centre Est',
        'www.ca-charente-perigord.fr': 'Charente Périgord',
        'www.ca-cmds.fr': 'Charente-Maritime Deux-Sèvres',
        'www.ca-corse.fr': 'Corse',
        'www.ca-cotesdarmor.fr': 'Côtes d\'Armor',
        'www.ca-des-savoie.fr': 'Des Savoie',
        'www.ca-finistere.fr': 'Finistere',
        'www.ca-franchecomte.fr': 'Franche-Comté',
        'www.ca-guadeloupe.fr': 'Guadeloupe',
        'www.ca-illeetvilaine.fr': 'Ille-et-Vilaine',
        'www.ca-languedoc.fr': 'Languedoc',
        'www.ca-loirehauteloire.fr': u'Loire Haute Loire',
        'www.ca-lorraine.fr': 'Lorraine',
        'www.ca-martinique.fr': 'Martinique Guyane',
        'www.ca-morbihan.fr': 'Morbihan',
        'www.ca-nmp.fr': 'Nord Midi-Pyrénées',
        'www.ca-nord-est.fr': 'Nord Est',
        'www.ca-norddefrance.fr': 'Nord de France',
        'www.ca-normandie-seine.fr': 'Normandie Seine',
        'www.ca-normandie.fr': 'Normandie',
        'www.ca-paris.fr': 'Ile-de-France',
        'www.ca-pca.fr': 'Provence Côte d\'Azur',
        'www.ca-reunion.fr': 'Réunion',
        'www.ca-sudmed.fr': 'Sud Méditerranée',
        'www.ca-sudrhonealpes.fr': 'Sud Rhône Alpes',
        'www.ca-toulouse31.fr': 'Toulouse 31',
        'www.ca-tourainepoitou.fr': 'Tourraine Poitou',
        'www.ca-valdefrance.fr': 'Val de France',
        'www.ca-pyrenees-gascogne.fr': 'Pyrénées Gascogne',
    }
    region_choices = OrderedDict([
        (website, u'%s (%s)' % (region, website)) for website, region in sorted(region_choices.items())
    ])

    region_aliases = {
        'm.ca-alpesprovence.fr': 'www.ca-alpesprovence.fr',
        'm.ca-alsace-vosges.fr': 'www.ca-alsace-vosges.fr',
        'm.ca-anjou-maine.fr': 'www.ca-anjou-maine.fr',
        'm.ca-aquitaine.fr': 'www.ca-aquitaine.fr',
        'm.ca-atlantique-vendee.fr': 'www.ca-atlantique-vendee.fr',
        'm.ca-briepicardie.fr': 'www.ca-briepicardie.fr',
        'm.ca-cb.fr': 'www.ca-cb.fr',
        'm.ca-centrefrance.fr': 'www.ca-centrefrance.fr',
        'm.ca-centreloire.fr': 'www.ca-centreloire.fr',
        'm.ca-centreouest.fr': 'www.ca-centreouest.fr',
        'm.ca-centrest.fr': 'www.ca-centrest.fr',
        'm.ca-charente-perigord.fr': 'www.ca-charente-perigord.fr',
        'm.ca-cmds.fr': 'www.ca-cmds.fr',
        'm.ca-corse.fr': 'www.ca-corse.fr',
        'm.ca-cotesdarmor.fr': 'www.ca-cotesdarmor.fr',
        'm.ca-des-savoie.fr': 'www.ca-des-savoie.fr',
        'm.ca-finistere.fr': 'www.ca-finistere.fr',
        'm.ca-franchecomte.fr': 'www.ca-franchecomte.fr',
        'm.ca-guadeloupe.fr': 'www.ca-guadeloupe.fr',
        'm.ca-illeetvilaine.fr': 'www.ca-illeetvilaine.fr',
        'm.ca-languedoc.fr': 'www.ca-languedoc.fr',
        'm.ca-loirehauteloire.fr': 'www.ca-loirehauteloire.fr',
        'm.ca-lorraine.fr': 'www.ca-lorraine.fr',
        'm.ca-martinique.fr': 'www.ca-martinique.fr',
        'm.ca-morbihan.fr': 'www.ca-morbihan.fr',
        'm.ca-nmp.fr': 'www.ca-nmp.fr',
        'm.ca-nord-est.fr': 'www.ca-nord-est.fr',
        'm.ca-norddefrance.fr': 'www.ca-norddefrance.fr',
        'm.ca-normandie-seine.fr': 'www.ca-normandie-seine.fr',
        'm.ca-normandie.fr': 'www.ca-normandie.fr',
        'm.ca-paris.fr': 'www.ca-paris.fr',
        'm.ca-pca.fr': 'www.ca-pca.fr',
        'm.ca-reunion.fr': 'www.ca-reunion.fr',
        'm.ca-sudmed.fr': 'www.ca-sudmed.fr',
        'm.ca-sudrhonealpes.fr': 'www.ca-sudrhonealpes.fr',
        'm.ca-toulouse31.fr': 'www.ca-toulouse31.fr',
        'm.ca-tourainepoitou.fr': 'www.ca-tourainepoitou.fr',
        'm.ca-valdefrance.fr': 'www.ca-valdefrance.fr',
        'm.lefil.com': 'www.ca-pyrenees-gascogne.fr',
    }

    BROWSER = CreditAgricoleBrowser

    CONFIG = BackendConfig(
        Value('website', label='Caisse Régionale', choices=region_choices, aliases=region_aliases),
        ValueBackendPassword('login', label='Identifiant à 11 chiffres', masked=False, regexp=r'\d{11}'),
        ValueBackendPassword('password', label='Code personnel à 6 chiffres', regexp=r'\d{6}')
    )

    accepted_document_types = (DocumentTypes.STATEMENT,)

    def create_default_browser(self):
        region_website = self.config['website'].get()

        return self.create_browser(
            region_website, self.config['login'].get(), self.config['password'].get(), woob=self.woob
        )

    # Accounts methods
    def get_account(self, _id):
        return find_object(self.iter_accounts(), id=_id, error=AccountNotFound)

    def iter_accounts(self):
        return self.browser.iter_accounts()

    # Transactions methods
    def iter_history(self, account):
        if account.type == Account.TYPE_CARD:
            return self.filter_transactions(account, coming=False)
        return self.browser.iter_history(account, coming=False)

    def iter_coming(self, account):
        if account.type == Account.TYPE_CARD:
            return self.filter_transactions(account, coming=True)
        return []

    def filter_transactions(self, account, coming):
        today = date.today()

        def switch_to_date(obj):
            if hasattr(obj, 'date'):
                return obj.date()
            return obj

        for tr in self.browser.iter_history(account, coming):
            is_coming = switch_to_date(tr.date) > today
            if is_coming == coming:
                yield tr
            elif coming:
                break

    # Wealth methods
    def iter_investment(self, account):
        return self.browser.iter_investment(account)

    def iter_market_orders(self, account):
        return self.browser.iter_market_orders(account)

    # Recipient & Transfer methods
    def iter_transfer_recipients(self, account):
        if not isinstance(account, Account):
            account = self.get_account(account)

        for rcpt in self.browser.iter_transfer_recipients(account):
            if not is_iban_valid(rcpt.iban):
                self.logger.info('Skipping recipient with invalid iban "%s"', rcpt.iban)
            else:
                yield rcpt

    def new_recipient(self, recipient, **params):
        return self.browser.new_recipient(recipient, **params)

    def init_transfer(self, transfer, **params):
        return self.browser.init_transfer(transfer, **params)

    def execute_transfer(self, transfer, **params):
        return self.browser.execute_transfer(transfer, **params)

    # Profile method
    def get_profile(self):
        if not hasattr(self.browser, 'get_profile'):
            raise NotImplementedError()
        return self.browser.get_profile()

    def iter_emitters(self):
        return self.browser.iter_emitters()

    # Documents methods
    def get_document(self, _id):
        subid = _id.rsplit('_', 1)[0]
        subscription = self.get_subscription(subid)

        return find_object(self.iter_documents(subscription), id=_id, error=DocumentNotFound)

    def iter_subscription(self):
        if not hasattr(self.browser, 'iter_subscription'):
            raise NotImplementedError()
        return self.browser.iter_subscription()

    def iter_documents(self, subscription):
        if not hasattr(self.browser, 'iter_documents'):
            raise NotImplementedError()
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)
        return self.browser.iter_documents(subscription)

    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)
        return self.browser.download_document(document)

    def iter_resources(self, objs, split_path):
        if Account in objs:
            self._restrict_level(split_path)
            return self.iter_accounts()
        if Subscription in objs:
            self._restrict_level(split_path)
            return self.iter_subscription()
