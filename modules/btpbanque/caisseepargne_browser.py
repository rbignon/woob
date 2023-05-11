# Copyright(C) 2017      Edouard Lambert
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

from woob_modules.caissedepargne.browser import CaisseEpargne


__all__ = ['CaisseEpargneBrowser']


class CaisseEpargneBrowser(CaisseEpargne):
    BASEURL = 'https://www.btp-banque.fr'
    CENET_URL = 'https://www.entreprises.btp-banque.fr'
    enseigne = 'btp'

    login = CaisseEpargne.login.with_urls(
        r'https://www.icgauth.btp-banque.fr/se-connecter/sso'
    )
    js_file = CaisseEpargne.js_file.with_urls(
        r'https://www.icgauth.btp-banque.fr/se-connecter/main\..*.js$',
        r'https://www.caisse-epargne.fr/espace-client/main\..*\.js',
        r'https://www.caisse-epargne.fr/gestion-client/credit-immobilier/main\..*\.js',
        r'https://www.caisse-epargne.fr/espace-gestion/pret-personnel/main\..*\.js',
    )
    config_page = CaisseEpargne.config_page.with_urls(
        r'https://www.btp-banque.fr/ria/pas/configuration/config.json\?ts=(?P<timestamp>.*)',
    )
