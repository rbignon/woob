# -*- coding: utf-8 -*-

# Copyright(C) 2019 Sylvie Ye
#
# This file is part of woob.
#
# woob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# woob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with woob. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

from woob.browser.pages import LoggedPage, JsonPage, HTMLPage
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanText, Format
from woob.browser.elements import ItemElement, method
from woob.capabilities.profile import Profile
from woob.capabilities.base import NotAvailable


class ProfilePage(LoggedPage, JsonPage):
    @method
    class get_profile(ItemElement):
        klass = Profile

        obj_name = Format('%s %s', Dict('name/firstName'), Dict('name/lastName'))
        obj_country = Dict('mailingAddress/country')
        obj_phone = Dict('phones/0/number', default=NotAvailable)
        obj_email = Dict('emailAddress')

        obj_address = CleanText(Format(
            '%s %s %s %s %s %s %s',
            Dict('mailingAddress/address1'),
            Dict('mailingAddress/address2'),
            Dict('mailingAddress/address3'),
            Dict('mailingAddress/address4'),
            Dict('mailingAddress/city'),
            Dict('mailingAddress/postCode'),
            Dict('mailingAddress/country')
        ))


class UselessProfilePage(LoggedPage, HTMLPage):
    # We land here after going away from bourse website.
    # We are redirected to this, we can't choose to land on accounts list, only here.
    # This page is just for staying logged.
    pass
