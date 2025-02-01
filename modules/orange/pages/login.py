# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Vincent Paredes
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

from woob.browser.filters.html import Attr
from woob.browser.filters.standard import CleanText, Format
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, RawPage

from .captcha import CaptchaPage


class LoginPage(CaptchaPage):
    def has_captcha(self):
        return Attr('//img[contains(@alt, "captcha")]', "alt", default=None)(self.doc)


class PasswordPage(JsonPage):
    ENCODING = "utf-8"

    def get_change_password_message(self):
        if self.doc.get("step") == "mandatory":
            # The password expired message on the website is fetched from a javascript file.
            return "Votre mot de passe actuel n’est pas suffisamment sécurisé et doit être renforcé."


class ManageCGI(HTMLPage):
    pass


class HomePage(LoggedPage, HTMLPage):
    def get_error_message(self):
        return Format(
            "%s %s",
            CleanText('//div[has-class("modal-dialog")]//h3'),
            CleanText('//div[has-class("modal-dialog")]//p[1]'),
        )(self.doc)


class PortalPage(LoggedPage, RawPage):
    pass
