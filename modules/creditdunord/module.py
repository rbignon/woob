# -*- coding: utf-8 -*-

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

from __future__ import unicode_literals

from collections import OrderedDict
import re

from unidecode import unidecode

from woob.capabilities.bank import Account
from woob.capabilities.bank.pfm import CapBankMatching
from woob.capabilities.base import find_object
from woob.capabilities.wealth import CapBankWealth
from woob.capabilities.profile import CapProfile
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword, Value

from .browser import CreditDuNordBrowser


__all__ = ['CreditDuNordModule']


class CreditDuNordModule(Module, CapBankWealth, CapProfile, CapBankMatching):
    NAME = 'creditdunord'
    MAINTAINER = 'Romain Bignon'
    EMAIL = 'romain@weboob.org'
    VERSION = '2.1'
    DESCRIPTION = u'Crédit du Nord, Banque Courtois, Kolb, Nuger, Laydernier, Tarneaud, Société Marseillaise de Crédit'
    LICENSE = 'LGPLv3+'

    websites = {
        'www.credit-du-nord.fr': 'Crédit du Nord',
        'www.banque-courtois.fr': 'Banque Courtois',
        'www.banque-kolb.fr': 'Banque Kolb',
        'www.banque-laydernier.fr': 'Banque Laydernier',
        'www.banque-nuger.fr': 'Banque Nuger',
        'www.banque-rhone-alpes.fr': 'Banque Rhône-Alpes',
        'www.tarneaud.fr': 'Tarneaud',
        'www.smc.fr': 'Société Marseillaise de Crédit',
    }
    website_choices = OrderedDict([
        (k, u'%s (%s)' % (v, k))
        for k, v in sorted(websites.items(), key=lambda k_v: (k_v[1], k_v[0]))
    ])
    CONFIG = BackendConfig(
        Value('website', label='Banque', choices=website_choices, default='www.credit-du-nord.fr'),
        ValueBackendPassword('login', label='Identifiant', masked=False),
        ValueBackendPassword('password', label='Code confidentiel')
    )
    BROWSER = CreditDuNordBrowser

    def create_default_browser(self):
        browser = self.create_browser(
            self.config['login'].get(),
            self.config['password'].get(),
            weboob=self.weboob,
        )
        browser.BASEURL = 'https://%s' % self.config['website'].get()
        if browser.BASEURL != 'https://www.credit-du-nord.fr':
            self.logger.warning('Please use the dedicated module instead of creditdunord')
        return browser

    def iter_accounts(self):
        for account in self.browser.iter_accounts():
            yield account

    def match_account(self, account, old_accounts):
        """Match an account in `old_accounts` corresponding to `account`.

        When module is changing profondly certain account attributes (id, umber, label, type)
        this CapBankMatching method help to compare an account with all other ones,
        previously in database. Hence matching is done on specificities chosen here.
        If it matches, then the old account matched takes on the new attribute values.
        If it does not match, the evaluated account is considered a new one (added in database).

        :param account: newly found account to search for
        :type account: :class:`Account`
        :param old_accounts: candidates accounts from a previous sync
        :type old_accounts: iter[:class:`Account`]
        :return: the corresponding account from `old_accounts`, or `None` if none matches
        :rtype: :class:`Account`
        """

        # try first matching on number and type
        match = find_object(old_accounts, number=account.number, type=account.type)

        matching_label = re.match(r'(.+) - .+', account.label)
        if matching_label:
            matching_label = unidecode(matching_label.group(1).upper())  # accents in the new labels

        # second, on label for market accounts
        if not match and matching_label and 'TITRES' in account.label.upper():
            # those were wrongly typed as market in previous module version
            # but we can match on part of the label
            # ex: 'PEA Estimation Titres - Toto Tata' --> 'PEA ESTIMATION TITRES' in old website
            markets = [
                acc for acc in old_accounts
                if acc.type == Account.TYPE_MARKET and matching_label in acc.label
            ]
            if len(markets) == 1:
                match = markets[0]

        # finally, on label and number when type has changed
        # ex: 'ETOILE AVANCE' was loan but is now 'Étoile avance - Toto Tata' a revolving credit
        if not match and matching_label:
            markets = [acc for acc in old_accounts if acc.number == account.number and matching_label in acc.label]
            if len(markets) == 1:
                match = markets[0]

        if match:
            return match

        self.logger.warning('Did not match this account to any previously known account: %s.', account.label)
        return None  # This account is then added as a new one when it is not matched with a pre-existing one

    def iter_history(self, account):
        for tr in self.browser.iter_history(account):
            if not tr._is_coming:
                yield tr

    def iter_coming(self, account):
        for tr in self.browser.iter_history(account, coming=True):
            if tr._is_coming:
                yield tr

    def iter_investment(self, account):
        return self.browser.iter_investment(account)

    def get_profile(self):
        return self.browser.get_profile()
