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

from woob.browser.elements import ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanText, Date, Field, Format
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage
from woob.capabilities import NotAvailable
from woob.capabilities.address import PostalAddress
from woob.capabilities.profile import Person, Profile


class ProfileParPage(LoggedPage, HTMLPage):
    def get_subscriber(self):
        template_xpath = '//p[contains(@class, "panelAccount-label")]/span[strong[contains(text(), "%s")]]'
        # Civilé
        # Nom
        # Prénom
        if CleanText(template_xpath % "Civilité")(self.doc):
            subscriber = Format(
                "%s %s %s",
                CleanText(template_xpath % "Civilité" + "/following::span[1]"),
                CleanText(template_xpath % "Nom :" + "/following::span[1]"),
                CleanText(template_xpath % "Prénom :" + "/following::span[1]"),
            )(self.doc)

        # Prénom / Nom
        elif CleanText(template_xpath % "Prénom / Nom")(self.doc):
            subscriber = CleanText(template_xpath % "Prénom / Nom" + "/following::span[1]")(self.doc)
        # Nom
        else:
            subscriber = CleanText(
                '//p[contains(@class, "panelAccount-label")]/span[strong[text()="Nom :"]]/following::span[1]'
            )(self.doc)

        return subscriber


class ProfileApiParPage(LoggedPage, JsonPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_gender = CleanText(Dict("identity/salutation", default=None), default=NotAvailable)
        obj_firstname = CleanText(Dict("identity/firstName", default=None), default=NotAvailable)
        obj_lastname = CleanText(Dict("identity/lastName", default=None), default=NotAvailable)
        obj_email = CleanText(Dict("contactInformation/email/address", default=None), default=NotAvailable)
        obj_mobile = CleanText(Dict("contactInformation/mobile/number", default=None), default=NotAvailable)
        obj_birth_date = Date(CleanText(Dict("identity/birth/date", default="")), default=NotAvailable)
        obj_birth_place = CleanText(Dict("identity/birth/city", default=""))

        def obj__subscriber(self):
            gender = Field("gender")(self) or ""
            firstname = Field("firstname")(self) or ""
            lastname = Field("lastname")(self) or ""

            subscriber = " ".join([el for el in (gender, firstname, lastname) if el])
            return subscriber or NotAvailable

    def get_name(self):
        return CleanText(Dict("identity/name", default=None), default=NotAvailable)(self.doc)


class ProfileProPage(LoggedPage, HTMLPage):
    def get_profile(self):
        pr = Profile()

        pr.email = CleanText('//input[@id="profile_email"]/@value')(self.doc)

        pr._subscriber = pr.name = Format(
            "%s %s",
            CleanText('//input[@id="profile_lastName"]/@value'),
            CleanText('//input[@id="profile_firstName"]/@value'),
        )(self.doc)

        pr.phone = CleanText('//div[contains(@class, "main-header-profile")][1]//div[@class="h2"]')(self.doc)

        return pr


class PostalAddressPage(LoggedPage, JsonPage):
    @method
    class get_postal_adress(ItemElement):
        klass = PostalAddress

        obj_full_address = CleanText(Dict("postalAddress", default=None), default=NotAvailable)
