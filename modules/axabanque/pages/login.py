# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from io import BytesIO

from weboob.exceptions import BrowserBanned, ActionNeeded, BrowserUnavailable
from weboob.browser.pages import HTMLPage, RawPage, JsonPage, PartialHTMLPage
from weboob.browser.filters.json import Dict
from weboob.browser.filters.standard import CleanText
from weboob.tools.captcha.virtkeyboard import VirtKeyboard, VirtKeyboardError


class MyVirtKeyboard(VirtKeyboard):
    margin = 5, 5, 5, 5
    color = (255, 255, 255)

    symbols = {
        '0': '962575659eb1bb72b15f856c0358c644',
        '1': '36ccbc0fff397cef567b5be362127484',
        '2': 'b823b3078cbfa1707ecbf8b9a92dea44',
        '3': 'f4790e47f878eba58ef93cfd6956726b',
        '4': '577620e004518fb057cc704842d59245',
        '5': '01e11c7a7092f2f7ec119b78be605923',
        '6': '0b7b051871b6bf4e2c91282cfcae09bc',
        '7': '920313cbddda9934447d8f1daa71e76b',
        '8': 'bdb35b451e6de3fb7221f50669fe52fb',
        '9': '1ee5fdfd7877ec9e0a957e14db5d29e6',
    }

    coords = {
        '0': (0, 0, 40, 40),
        '1': (40, 0, 80, 40),
        '2': (80, 0, 120, 40),
        '3': (120, 0, 160, 40),
        '4': (0, 40, 40, 80),
        '5': (40, 40, 80, 80),
        '6': (80, 40, 120, 80),
        '7': (120, 40, 160, 80),
        '8': (0, 80, 40, 120),
        '9': (40, 80, 80, 120),
        '10': (80, 80, 120, 120),
        '11': (120, 80, 160, 120),
        '12': (0, 120, 40, 160),
        '13': (40, 120, 80, 160),
        '14': (80, 120, 120, 160),
        '15': (120, 120, 160, 160),
    }

    def __init__(self, page):
        VirtKeyboard.__init__(self, BytesIO(page.content), self.coords, self.color, convert='RGB')

        self.check_symbols(self.symbols, None)

    def get_string_code(self, string):
        return ','.join(self.get_position_from_md5(self.symbols[c]) for c in string)

    def get_position_from_md5(self, md5):
        for k, v in self.md5.items():
            if v == md5:
                return k

    def check_color(self, pixel):
        return pixel[0] > 0


class KeyboardPage(RawPage):
    def get_password(self, password):
        vk_passwd = None

        try:
            vk = MyVirtKeyboard(self)
            vk_passwd = vk.get_string_code(password)
        except VirtKeyboardError as e:
            self.logger.error(e)

        return vk_passwd


class LoginPage(JsonPage):
    def check_error(self):
        return (not Dict('errors')(self.doc)) is False

    def get_url(self):
        return CleanText(Dict('datas/url', default=''))(self.doc)


class ChangepasswordPage(HTMLPage):
    def on_load(self):
        raise ActionNeeded()


class PredisconnectedPage(HTMLPage):
    def on_load(self):
        raise BrowserBanned()


class DeniedPage(HTMLPage):
    def on_load(self):
        raise ActionNeeded()


class AccountSpaceLogin(JsonPage):
    def get_error_link(self):
        return self.doc.get('informationUrl')


class ErrorPage(PartialHTMLPage):
    def on_load(self):
        error_msg = (
            CleanText('//p[contains(text(), "temporairement indisponible")]')(self.doc),
            CleanText('//p[contains(text(), "maintenance est en cours")]')(self.doc),
            # parsing for false 500 error page
            CleanText('//div[contains(@class, "error-page")]//span[contains(@class, "subtitle") and contains(text(), "Chargement de page impossible")]')(self.doc)
        )

        for error in error_msg:
            if error:
                raise BrowserUnavailable(error)


class AuthorizePage(HTMLPage):
    def on_load(self):
        form = self.get_form()
        form.submit()
