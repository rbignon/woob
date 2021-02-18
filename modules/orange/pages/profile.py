# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Vincent Paredes
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

from weboob.browser.elements import ItemElement, method
from weboob.browser.filters.json import Dict
from weboob.browser.pages import HTMLPage, LoggedPage, JsonPage
from weboob.capabilities.profile import Profile, Person
from weboob.browser.filters.standard import CleanText, Format, Field


class ProfileParPage(LoggedPage, JsonPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_gender = CleanText(Dict('identity/salutation'))
        obj_firstname = CleanText(Dict('identity/firstName'))
        obj_lastname = CleanText(Dict('identity/lastName'))
        obj_email = CleanText(Dict('contactInformation/email/address'))
        obj_mobile = CleanText(Dict('contactInformation/mobile/number'))
        obj__subscriber = Format('%s %s %s', Field('gender'), Field('firstname'), Field('lastname'))


class ProfileProPage(LoggedPage, HTMLPage):
    def get_profile(self):
        pr = Profile()

        pr.email = CleanText('//input[@id="profile_email"]/@value')(self.doc)

        pr.name = Format(
            '%s %s',
            CleanText('//input[@id="profile_lastName"]/@value'),
            CleanText('//input[@id="profile_firstName"]/@value'),
        )(self.doc)

        pr.phone = CleanText('//div[contains(@class, "main-header-profile")][1]//div[@class="h2"]')(self.doc)

        return pr
