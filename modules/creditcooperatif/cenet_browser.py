# -*- coding: utf-8 -*-

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

from weboob.browser import AbstractBrowser, URL
from weboob.capabilities.bank import Account
from .linebourse_browser import LinebourseAPIBrowser

from .pages import JsFilePage, LoginPage, NewLoginPage, ConfigPage


__all__ = ['CenetBrowser']


class CenetBrowser(AbstractBrowser):
    PARENT = 'caissedepargne'
    PARENT_ATTR = 'package.cenet.browser.CenetBrowser'
    BASEURL = 'https://www.espaceclient.credit-cooperatif.coop/'

    login = URL(
        r'https://www.credit-cooperatif.coop/authentification/manage\?step=identification&identifiant=(?P<login>.*)',
        r'https://.*/login.aspx',
        LoginPage
    )

    new_login = URL(r'https://www.credit-cooperatif.coop/se-connecter/sso', NewLoginPage)
    js_file = URL(r'https://www.credit-cooperatif.coop/se-connecter/main-.*.js$', JsFilePage)
    config_page = URL('https://www.credit-cooperatif.coop/ria/pas/configuration/config.json', ConfigPage)

    LINEBOURSE_BROWSER = LinebourseAPIBrowser
    MARKET_URL = 'https://www.offrebourse.com'

    def has_no_history(self, account):
        return account.type == Account.TYPE_LOAN
