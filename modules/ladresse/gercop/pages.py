# flake8: compatible

# Copyright(C) 2022 Thomas Touhey <thomas@touhey.fr>
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

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanText, Coalesce, Date, Map, Regexp, Upper
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, RawPage
from woob.capabilities.address import PostalAddress
from woob.capabilities.bill import Document
from woob.capabilities.profile import Person


class LoginPage(RawPage):
    pass


class HomePage(LoggedPage, RawPage):
    pass


class PasswordExpiredPage(LoggedPage, HTMLPage):
    def get_error_message(self):
        return CleanText(
            '//div[@id="connexionContainer"]//div[@class="form-group bold"]',
        )(self.doc)


class AuthenticatePage(JsonPage):
    def get_authentication_result(self):
        return {
            "authentication": Dict("authentication")(self.doc),
            "message": Dict("authenticationResult")(self.doc),
        }


class ProfilePage(LoggedPage, JsonPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_name = CleanText(Dict("Locataire/computedName"))
        obj_gender = Map(
            Upper(Dict("Locataire/civilites_libelle")),
            {
                "M.": "male",
                "MME.": "female",
            },
        )

        obj_email = CleanText(Dict("Locataire/email/0/libelle"))
        obj_phone = CleanText(
            Coalesce(
                Dict("Locataire/telephone_mobile/0/libelle", default=None),
                Dict("Locataire/telephone_dom/0/libelle", default=None),
            )
        )

        class obj_postal_address(ItemElement):
            klass = PostalAddress

            obj_street = CleanText(Dict("Locataire/route"))
            obj_postal_code = CleanText(Dict("Locataire/postal_code"))
            obj_city = CleanText(Dict("Locataire/locality"))
            obj_country = CleanText(Dict("Locataire/country"))


class DocumentCategoriesPage(LoggedPage, JsonPage):
    def iter_categories(self):
        for obj in self.doc["data"]["Classeurs"]:
            yield obj


class DocumentsPage(LoggedPage, JsonPage):
    @method
    class iter_documents(DictElement):
        item_xpath = "data/Documents"

        # TODO: Manage pagination when a case with enough documents
        #       has been found.
        class item(ItemElement):
            klass = Document

            obj_id = CleanText(Dict("id"))
            obj_label = CleanText(Dict("name"))
            obj_format = Map(
                CleanText(Dict("mime_type")),
                {
                    "application/pdf": "pdf",
                },
            )
            obj_date = Date(CleanText(Dict("date_commit_libelle")))

            # NOTE: Since the categories on the Gercop website are
            #       dynamic and are named by the company or organization
            #       that manages the local platform, it is not possible
            #       to have a reliable document type detection here.

            # Extract the number, e.g. 'AVIS_22-05-001-23456-789-00.pdf'.
            obj_number = Regexp(
                Dict("name"),
                r".+_([0-9-]+)\.[a-z]+",
            )


# End of file.
