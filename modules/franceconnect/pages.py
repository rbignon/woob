# Copyright(C) 2012-2020 Powens
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

import re

from woob.browser.filters.javascript import JSValue
from woob.browser.filters.standard import CleanText
from woob.browser.pages import HTMLPage


class AuthorizePage(HTMLPage):
    def get_error_message(self):
        return CleanText("//h1[@data-testid=error-section-title]")(self.doc)

    def redirect(self):
        # just one form on this page, so get_form() should work but it's better to put a more restrictive xpath
        form = self.get_form(xpath='//form[@action="/confirm-redirect-client"]')
        form.submit()


class AmeliLoginPage(HTMLPage):
    def login(self, username, password):
        # CAUTION, form id, username and password keys are not the same than the one of standard ameli login page
        form = self.get_form(id="connexion_form")
        form["j_username"] = username
        form["j_password"] = password
        form.submit()


class WrongPassAmeliLoginPage(HTMLPage):
    def get_error_message(self):
        return CleanText('//div[@id="divErreur"]')(self.doc)


class ImpotsLoginAccessPage(HTMLPage):
    def login(self, login, password, url, auth_type=""):
        form = self.get_form(id="formulairePrincipal")
        form.url = url
        form["lmAuth"] = "LDAP"
        form["authType"] = auth_type
        form["spi"] = login
        form["pwd"] = password
        form.submit()

    def get_url_context(self):
        return "/GetContexte"

    def get_url_login_password(self):
        return "/"


class MessageResultPage(HTMLPage):
    status = None
    message = None

    def load_status_and_message_from_post_message(self):
        if not self.status or not self.message:
            # parent.postMessage(args...)
            first_argument = JSValue(CleanText('//script[contains(text(), "parent.postMessage")]'), nth=0)(self.doc)
            # The message is separated in 2 parts with a comma
            message_parts = first_argument.split(",")
            assert len(message_parts) == 2, "Unexpected message from France Connect impôts"
            self.status, self.message = message_parts


class ImpotsGetContextPage(MessageResultPage):
    def has_wrong_login(self):
        self.load_status_and_message_from_post_message()
        return self.message == "EXISTEPAS"

    def is_blocked(self):
        self.load_status_and_message_from_post_message()
        return self.message == "BLOCAGE"

    def has_next_step(self):
        self.load_status_and_message_from_post_message()
        return self.status == "ctx" and self.message == "LMDP"


class ImpotsLoginAELPage(MessageResultPage):
    def get_next_url(self):
        self.load_status_and_message_from_post_message()
        assert re.match(r"^https?://.*$", self.message), f"Unexpected message: {self.message}"
        return self.message

    def has_wrong_password(self):
        self.load_status_and_message_from_post_message()
        # 4005 is the code for a wrong password followed by the number of remaining
        # attempts
        return self.status == "lmdp" and re.match(r"^4005:\d+$", self.message)

    def get_remaining_login_attempts(self):
        self.load_status_and_message_from_post_message()
        return re.match(r"^4005:(\d+)$", self.message).group(1)

    def is_status_ok(self):
        self.load_status_and_message_from_post_message()
        return self.status == "ok"
