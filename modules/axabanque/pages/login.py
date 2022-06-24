# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
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

from woob.exceptions import (
    BrowserUserBanned, ActionNeeded, BrowserUnavailable, BrowserPasswordExpired,
)
from woob.browser.pages import HTMLPage, RawPage, JsonPage, PartialHTMLPage
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanText


class LoginPage(JsonPage):
    def check_error(self):
        return (not Dict('errors')(self.doc)) is False

    def get_url(self):
        return CleanText(Dict('datas/url', default=''))(self.doc)

    def password_expired(self):
        return 'changebankpassword' in CleanText(Dict('datas/url'))(self.doc)


class ChangepasswordPage(HTMLPage):
    def on_load(self):
        raise BrowserPasswordExpired()


class PredisconnectedPage(HTMLPage):
    def on_load(self):
        raise BrowserUserBanned()


class DeniedPage(HTMLPage):
    def on_load(self):
        raise ActionNeeded()


class LoginEndPage(RawPage):
    # just a pass-through page at the end of login
    # need is_here to avoid confusion with .pages.wealth.WealthAccountsPage
    def is_here(self):
        return self.response.status_code == 302


class AccountSpaceLogin(JsonPage):
    def get_error_link(self):
        return self.doc.get('informationUrl')

    def get_error_message(self):
        return self.doc.get('informationMessage')

    def get_password_information_message(self):
        return self.doc.get('passwordInformationMessage')


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


class InfiniteLoopPage(HTMLPage):
    pass


class AuthorizePage(HTMLPage):
    def on_load(self):
        form = self.get_form()
        form.submit()

