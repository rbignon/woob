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

# flake8: compatible

from woob.browser.pages import JsonPage, LoggedPage, RawPage


class HomePage(LoggedPage, RawPage):
    pass


class LoginPage(RawPage):
    pass


class AuthenticationPage(JsonPage):
    def get_password_json(self):
        return self.doc

    def get_public_key(self):
        return self.doc['header'][10:]

    def get_pre_otp_json(self):
        return self.doc

    def is_pre_otp_here(self):
        return self.doc['callbacks'][1]['output'][2]['value'][0] == 'Send the code'

    def get_otp_json(self):
        return self.doc
