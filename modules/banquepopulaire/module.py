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

from collections import OrderedDict

from woob.capabilities.bank import Account, AccountNotFound
from woob.capabilities.bank.wealth import CapBankWealth
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import Value, ValueBackendPassword, ValueTransient

from .browser import BanquePopulaire


__all__ = ['BanquePopulaireModule']


class BanquePopulaireModule(Module, CapBankWealth):
    NAME = 'banquepopulaire'
    MAINTAINER = 'Etienne RABY'
    EMAIL = 'mail@eraby.fr'
    DEPENDENCIES = ('caissedepargne', 'linebourse')
    DESCRIPTION = 'Banque Populaire'
    LICENSE = 'LGPLv3+'

#   Could be updated just by checking https://www.icgauth.banquepopulaire.fr/ria/pas/configuration/config.json
    cdetab_choices = {
        '13807': 'Grand Ouest',
        '14707': 'Alsace Lorraine Champagne',
        '10907': 'Aquitaine Centre Atlantique',
        '16807': 'Auvergne Rhone Alpes',
        '10807': 'Bourgogne Franche Comté',
        '13507': 'Nord',
        '16607': 'Sud',
        '14607': 'Mediterranée',
        '17807': 'Occitane',
        '10207': 'Rives de Paris',
        '18707': 'Val de France',
        'Padding': 'ZZ Do not use that entry',  # Ugly hack to avoid "v.tiny = True" in console.py:ask()
    }

    cdetab_choices = OrderedDict([
        (k, '%s ( %s )' % (v, k))
        for k, v in sorted(cdetab_choices.items(), key=lambda k_v: (k_v[1], k_v[0]))])

    CONFIG = BackendConfig(
        Value('cdetab', label='Région', choices=cdetab_choices, regexp=r'\d{5}'),
        ValueBackendPassword('login', label='Identifiant', masked=False, regexp=r'[a-zA-Z0-9]+'),
        ValueBackendPassword('password', label='Mot de passe'),
        ValueTransient('code_sms', regexp=r'\d{8}'),
        ValueTransient('code_emv', regexp=r'\d{8}'),
        ValueTransient('resume'),
        ValueTransient('request_information'),
    )

    BROWSER = BanquePopulaire

    def create_default_browser(self):
        return self.create_browser(
            "www.banquepopulaire.fr",
            self.config,
        )

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def get_account(self, _id):
        account = self.browser.get_account(_id)
        if account:
            return account
        else:
            raise AccountNotFound()

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_coming(self, account):
        return None

    def iter_investment(self, account):
        pass

    def iter_market_orders(self, account):
        pass

    def iter_contacts(self):
        pass

    def get_profile(self):
        pass

    def iter_subscription(self):
        pass

    def iter_documents(self, subscription):
        pass

    def get_document(self, _id):
        pass

    def download_document(self, document):
        pass

    def iter_resources(self, objs, split_path):
        if Account in objs:
            self._restrict_level(split_path)
            return self.iter_accounts()
