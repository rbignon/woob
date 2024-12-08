# Copyright(C) 2012 Kevin Pouget
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

from woob_modules.caissedepargne.browser import CaisseEpargne
from woob_modules.linebourse.browser import LinebourseAPIBrowser

__all__ = ['CaisseEpargneBrowser']


class CaisseEpargneBrowser(CaisseEpargne):
    BASEURL = 'https://www.credit-cooperatif.coop'
    CENET_URL = 'https://www.espaceclient.credit-cooperatif.coop'
    enseigne = 'ccoop'

    login = CaisseEpargne.login.with_urls(
        r'https://www.credit-cooperatif.coop/se-connecter/sso',
        r'https://(?P<domain>www.icgauth.[^/]+)/se-connecter/sso'
    )
    js_file = CaisseEpargne.js_file.with_urls(
        r'https://www.credit-cooperatif.coop/se-connecter/main\..*.js$',
        r'https://(?P<domain>www.icgauth.[^/]+)/se-connecter/main\..*.js$',
        r'https://www.caisse-epargne.fr/espace-client/main-.*\.js',
        r'https://www.caisse-epargne.fr/espace-client/chunk-.*\.js',
        r'https://www.caisse-epargne.fr/gestion-client/credit-immobilier/main\..*\.js',
        r'https://www.caisse-epargne.fr/espace-gestion/pret-personnel/main\..*\.js',
    )
    config_page = CaisseEpargne.config_page.with_urls(r'https://www.credit-cooperatif.coop/ria/pas/configuration/config.json\?ts=(?P<timestamp>.*)')

    LINEBOURSE_BROWSER = LinebourseAPIBrowser

    def __init__(self, nuser, config, *args, **kwargs):
        kwargs['market_url'] = 'https://www.offrebourse.com'
        super(CaisseEpargneBrowser, self).__init__(nuser, config, *args, **kwargs)
