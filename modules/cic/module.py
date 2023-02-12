# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Julien Veyssier
# Copyright(C) 2012-2013 Romain Bignon
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

from woob.capabilities.bank import CapBankTransferAddRecipient, Account
from woob.capabilities.bill import CapDocument
from woob.capabilities.profile import CapProfile
from woob.capabilities.bank.pfm import CapBankMatching
from woob.capabilities.contact import CapContact
from woob.tools.backend import AbstractModule, BackendConfig
from woob.tools.value import ValueTransient

from .browser import CICBrowser


__all__ = ['CICModule']


class CICModule(AbstractModule, CapBankTransferAddRecipient, CapDocument, CapContact, CapProfile, CapBankMatching):
    NAME = 'cic'
    MAINTAINER = u'Julien Veyssier'
    EMAIL = 'julien.veyssier@aiur.fr'
    VERSION = '3.3.1'
    DEPENDENCIES = ('creditmutuel',)
    DESCRIPTION = u'CIC'
    LICENSE = 'LGPLv3+'

    BROWSER = CICBrowser
    PARENT = 'creditmutuel'

    ADDITIONAL_CONFIG = BackendConfig(
        ValueTransient('code', regexp=r'^\d{6}$'),
    )

    def create_default_browser(self):
        browser = self.create_browser(self.config, woob=self.woob)
        browser.new_accounts.urls.insert(0, "/mabanque/fr/banque/comptes-et-contrats.html")
        return browser

    def match_account(self, account, old_accounts):
        def match_card(old_card, card):
            """
            Match two cards, based on their numbers and/or their other attributes(label, balance, coming)
            """
            if hasattr(card, '_numbers') and card._numbers:
                # we try to match the based on the numbers
                if old_card.number in card._numbers:
                    return True

            # if the numbers do not match, we match the cards based on their other attributes
            return (
                old_card.label == card.label
                and old_card.coming == card.coming
                and old_card.balance == card.balance
            )

        # We define it only for cards
        if account.type != Account.TYPE_CARD:
            return super().match_account(account, old_accounts)

        for old_account in old_accounts:
            # filter based on type
            if old_account.type != Account.TYPE_CARD:
                continue

            # we match the two cards
            if match_card(old_account, account):
                return old_account

        return None
