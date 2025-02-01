# Copyright(C) 2012-2023  Powens
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

import hashlib
import re

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import Attr, HasElement
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanText, Date, Env, Field, Format, Regexp
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, RawPage, pagination
from woob.capabilities.address import PostalAddress
from woob.capabilities.base import NotAvailable
from woob.capabilities.bill import Document, DocumentTypes, Subscription
from woob.capabilities.profile import Person
from woob.tools.date import parse_french_date
from woob_modules.franceconnect.pages import AuthorizePage


class FCAuthorizePage(AuthorizePage):
    def is_ameli_disabled(self):
        return HasElement('//button[@id="fi-ameli" and @disabled="disabled"]')(self.doc)


class ImpotsPage(HTMLPage):
    @property
    def logged(self):
        return bool(CleanText('//button[@id="accederdeconnexion"]')(self.doc))


class HomePage(ImpotsPage):
    pass


class NoDocumentPage(LoggedPage, RawPage):
    pass


class ErrorDocumentPage(LoggedPage, RawPage):
    pass


class ThirdPartyDocPage(LoggedPage, JsonPage):
    @method
    class get_third_party_doc(ItemElement):
        klass = Document

        obj_id = Format("%s_%s", Dict("spiDec1"), Dict("dateNaisDec1"))
        obj_format = "json"
        obj_label = "Déclaration par un tiers"
        obj_type = DocumentTypes.OTHER

        def obj_url(self):
            return self.page.url


class ProfilePage(LoggedPage, HTMLPage):
    def get_documents_link(self):
        return self.doc.xpath('//a[contains(@title, "déclarations")]/@href')[0]

    def get_bills_link(self):
        return self.doc.xpath('//a[contains(@title, "résumé")]/@href')[0]

    @method
    class get_subscriptions(ListElement):
        class item(ItemElement):
            klass = Subscription

            obj_subscriber = Format("%s %s", CleanText('//span[@id="prenom"]'), CleanText('//span[@id="nom"]'))
            obj_id = Regexp(CleanText('//span[contains(text(), "N° fiscal")]'), r"N° fiscal : (\d+)")
            obj_label = Field("id")

    @method
    class get_profile(ItemElement):
        klass = Person

        obj_name = Format("%s %s", Field("firstname"), Field("lastname"))
        obj_firstname = CleanText('//span[@id="prenom"]')
        obj_lastname = CleanText('//span[@id="nom"]')
        obj_email = CleanText('//div[span[contains(text(), "Adresse électronique")]]/following-sibling::div/span')
        obj_mobile = CleanText(
            '//div[span[text()="Téléphone portable"]]/following-sibling::div/span', default=NotAvailable
        )
        obj_phone = CleanText('//div[span[text()="Téléphone fixe"]]/following-sibling::div/span', default=NotAvailable)
        obj_birth_date = Date(CleanText('//span[@id="datenaissance"]'), parse_func=parse_french_date)
        obj_birth_place = CleanText('//span[@id="lieunaissance"]')

        class obj_postal_address(ItemElement):
            klass = PostalAddress

            obj_full_address = Env("full_address", default=NotAvailable)
            obj_street = Env("street", default=NotAvailable)
            obj_postal_code = Env("postal_code", default=NotAvailable)
            obj_city = Env("city", default=NotAvailable)

            def parse(self, obj):
                full_address = CleanText('//span[@id="adressepostale"]')(self)
                self.env["full_address"] = full_address
                m = re.search(r"(\d{1,4}.*) (\d{5}) (.*)", full_address)
                if m:
                    street, postal_code, city = m.groups()
                    self.env["street"] = street
                    self.env["postal_code"] = postal_code
                    self.env["city"] = city


class DocumentsPage(LoggedPage, HTMLPage):
    @pagination
    @method
    class iter_documents(ListElement):
        item_xpath = '//ul[has-class("documents")]/li'

        def next_page(self):
            previous_year = CleanText(
                '//li[has-class("blocAnnee") and has-class("selected")]/following-sibling::li[1]/a', children=False
            )(self.page.doc)

            # only if previous_year is not None and different from current year,
            # else we return to page with current year and fall into infinite loop
            if previous_year:
                previous_year = int(Regexp(None, r"(\d{4})").filter(previous_year))

                current_year = int(
                    Regexp(
                        CleanText('//li[has-class("blocAnnee") and has-class("selected")]/a', children=False),
                        r"(\d{4})",
                    )(self.page.doc)
                )

                if previous_year >= current_year:
                    # if previous year is 'something 2078' website return page of current year
                    # previous_year has to be nothing but digit
                    # don't return anything to not fall into infinite loop, but something bad has happened
                    self.logger.error(
                        "pagination loop, previous_year: %s pagination is unexpectedly superior or equal to current_year: %s",
                        previous_year,
                        current_year,
                    )
                    return

                return self.page.browser.documents.build(params={"n": previous_year})

        class item(ItemElement):
            klass = Document

            obj__idEnsua = Attr('.//form/input[@name="idEnsua"]', "value")  # can be 64 or 128 char length

            def obj_id(self):
                # hash _idEnsua to reduce his size at 32 char
                hash = hashlib.sha1(Field("_idEnsua")(self).encode("utf-8")).hexdigest()
                return "%s_%s" % (Env("subid")(self), hash)

            obj_date = Date(Env("date"))
            obj_label = Env("label")
            obj_type = DocumentTypes.NOTICE
            obj_format = "pdf"
            obj_url = Format("/enp/Affichage_Document_PDF?idEnsua=%s", Field("_idEnsua"))

            def parse(self, el):
                label_ct = CleanText('./div[contains(@class, "texte")][has-class("hidden-xs")]')
                date = Regexp(label_ct, r"le ([\w\/]+?),", default=NotAvailable)(self)
                self.env["label"] = label_ct(self)

                if not date:
                    # take just the year in current page
                    year = CleanText(
                        '//li[has-class("blocAnnee") and has-class("selected")]/a',
                        children=False,
                        default=NotAvailable,
                    )(self)

                    if "sur les revenus de" in self.env["label"]:
                        # this kind of document always appear un july, (but we don't know the day)
                        date = "%s-07-01" % year
                    else:
                        date = "%s-01-01" % year
                self.env["date"] = date
