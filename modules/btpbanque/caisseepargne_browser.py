# -*- coding: utf-8 -*-

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

from weboob.browser import AbstractBrowser, URL

from .pages import JsFilePage, LoginPage, NewLoginPage, ConfigPage


__all__ = ['CaisseEpargneBrowser']


class CaisseEpargneBrowser(AbstractBrowser):
    PARENT = 'caissedepargne'
    PARENT_ATTR = 'package.browser.CaisseEpargne'

    BASEURL = 'https://www.btp-banque.fr'
    CENET_URL = 'https://www.entreprises.btp-banque.fr'

    login = URL(
        r'https://www.btp-banque.fr/authentification/manage\?step=identification&identifiant=(?P<login>.*)',
        r'https://.*/login.aspx',
        LoginPage
    )

    new_login = URL(r'https://www.btp-banque.fr/se-connecter/sso', NewLoginPage)
    js_file = URL(r'https://www.btp-banque.fr/se-connecter/main-.*.js$', JsFilePage)
    config_page = URL('https://www.btp-banque.fr/ria/pas/configuration/config.json', ConfigPage)
