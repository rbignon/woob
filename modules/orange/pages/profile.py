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
from weboob.capabilities import NotAvailable
from weboob.capabilities.profile import Profile, Person
from weboob.browser.filters.standard import CleanText, Format, Field


class ProfileParPage(LoggedPage, HTMLPage):
    def get_subscriber(self):
        template_xpath = '//p[contains(@class, "panelAccount-label")]/span[strong[contains(text(), "%s")]]'
        # Civilé
        # Nom
        # Prénom
        if CleanText(template_xpath % 'Civilité')(self.doc):
            subscriber = Format(
                '%s %s %s',
                CleanText(template_xpath % 'Civilité' + '/following::span[1]'),
                CleanText(template_xpath % 'Nom :' + '/following::span[1]'),
                CleanText(template_xpath % 'Prénom :' + '/following::span[1]')
            )(self.doc)

        # Prénom / Nom
        elif CleanText(template_xpath % 'Prénom / Nom')(self.doc):
            subscriber = CleanText(template_xpath % 'Prénom / Nom' + '/following::span[1]')(self.doc)
        # Nom
        else:
            subscriber = CleanText('//p[contains(@class, "panelAccount-label")]/span[strong[text()="Nom :"]]/following::span[1]')(self.doc)

        return subscriber


class ProfileApiParPage(LoggedPage, JsonPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_gender = CleanText(Dict('identity/salutation', default=None), default=NotAvailable)
        obj_firstname = CleanText(Dict('identity/firstName', default=None), default=NotAvailable)
        obj_lastname = CleanText(Dict('identity/lastName', default=None), default=NotAvailable)
        obj_email = CleanText(Dict('contactInformation/email/address'))
        obj_mobile = CleanText(Dict('contactInformation/mobile/number'))

        def obj__subscriber(self):
            gender = Field('gender')(self) or ''
            firstname = Field('firstname')(self) or ''
            lastname = Field('lastname')(self) or ''

            subscriber = ' '.join([el for el in (gender, firstname, lastname) if el])
            return subscriber or NotAvailable


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
