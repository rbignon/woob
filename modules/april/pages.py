# -*- coding: utf-8 -*-

# Copyright(C) 2020      Ludovic LANGE
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


from weboob.browser.pages import (
    JsonPage,
    LoggedPage,
)
from weboob.exceptions import (
    BrowserIncorrectPassword,
    BrowserUnavailable,
)
from weboob.browser.filters.json import Dict
from weboob.browser.filters.standard import (
    CleanText,
    Format,
    Coalesce,
    Date,
    CleanDecimal,
)
from weboob.capabilities.profile import Person
from weboob.capabilities.bill import DocumentTypes, Document
from weboob.browser.elements import ItemElement, DictElement, method
from weboob.capabilities.base import NotAvailable


class AprilJsonPage(JsonPage):
    def on_load(self):
        if (
            self.get("error")
            and self.get("statusCode")
            and (self.get("statusCode") == 401)
        ):
            raise BrowserIncorrectPassword("%s : %s" % (Dict("error"), Dict("message")))
        elif self.get("error") or self.get("status") or self.get("message"):
            raise BrowserUnavailable(
                "%d - %s : %s" % (Dict("status"), Dict("error"), Dict("message"))
            )


class LoginPage(AprilJsonPage):
    @property
    def logged(self):
        return "token" in self.doc

    def get_token(self):
        return Dict("token")(self.doc)

    def login(self, username, password):
        form = self.get_form(xpath='//form[has-class("loginForm")]')
        form["username"] = username
        form["password"] = password
        form.submit()


class ProfilePage(LoggedPage, AprilJsonPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_id = Dict("numeroPersonne")
        obj_name = Format(
            "%s %s", Dict("prenom"), Coalesce(Dict("nomNaissance"), Dict("nom"))
        )
        obj_address = CleanText(
            Format(
                "%s %s %s %s %s %s %s %s",
                Dict("adressePostale/numeroVoie"),
                Dict("adressePostale/codeVoie"),
                Dict("adressePostale/typeVoie"),
                Dict("adressePostale/libelleVoie"),
                Dict("adressePostale/mentionDistribution"),
                Dict("adressePostale/codePostal"),
                Dict("adressePostale/bureauDistributeur"),
                Dict("adressePostale/pays"),
            )
        )
        obj_country = Dict("adressePostale/pays", default=NotAvailable)
        obj_phone = Dict("telephoneDomicile", default=NotAvailable)
        obj_professional_phone = Dict("telephoneProfessionnel", default=NotAvailable)
        obj_email = Dict("email", default=NotAvailable)
        obj_birth_date = Date(Dict("dateNaissance"), default=NotAvailable)
        obj_firstname = Dict("prenom", default=NotAvailable)
        obj_lastname = Coalesce(Dict("nomNaissance"), Dict("nom"), NotAvailable)
        obj_mobile = Dict("telephonePersonnel", default=NotAvailable)
        obj_maiden_name = Dict("nomNaissance", default=NotAvailable)
        obj_children = CleanDecimal(Dict("nombreEnfantsACharge"), default=NotAvailable)
        obj_family_situation = Dict("situationFamiliale/libelle", default=NotAvailable)
        obj_job = Dict("profession", default=NotAvailable)
        obj_socioprofessional_category = Dict(
            "categorieSocioProfessionnelle/libelle", default=NotAvailable
        )

        def obj_gender(self):
            if not Dict("civilite"):
                return NotAvailable
            if Dict("civilite")(self) == "M":
                gender = "Male"
            else:
                gender = "Female"
            return gender


class DocumentsPage(JsonPage):
    @method
    class iter_documents(DictElement):
        ignore_duplicate = True

        class item(ItemElement):
            klass = Document
            obj_id = Dict("reference")
            obj_label = Dict("libelle")
            obj_date = Date(
                Dict("dateEmission", default=NotAvailable), default=NotAvailable
            )
            obj_format = "pdf"
            obj_url = Format("/api/documents/auth/%s", Dict("reference"))

            def obj_type(self):
                doc_type = Dict("typeDocument")(self)
                doc_label = Dict("libelle")(self)
                if (doc_type == "Courriers") or (doc_label == "Courrier du"):
                    otype = DocumentTypes.NOTICE
                elif doc_type == "Appel de cotisation":
                    otype = DocumentTypes.BILL
                elif doc_type in ["Conditions générales", "Dossier d'adhésion"]:
                    otype = DocumentTypes.CONTRACT
                else:
                    otype = DocumentTypes.OTHER
                return otype
