# -*- coding: utf-8 -*-

# Copyright(C) 2021 Vincent A
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

from __future__ import unicode_literals

from woob.browser.elements import method, ListElement, ItemElement
from woob.browser.filters.standard import (
    CleanText, DateTime, Env, Format, Regexp, Map,
)
from woob.browser.pages import (
    HTMLPage, Page, JsonPage, PartialHTMLPage,
)
from woob.capabilities.base import NotAvailable
from woob.capabilities.parcel import Event, Parcel, ParcelState


class FormPage(HTMLPage):
    def submit(self, number, postal_code):
        form = self.get_form(id="SuiviExpedition_Index_Form_Base")
        form["NumeroExpedition"] = number
        form["CodePostal"] = postal_code
        form.submit()


class ParentPage:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sub_page = self.SubPage(self, self.browser, self.response, self.params)


class SubPage(Page):
    def __init__(self, parent, *args, **kwargs):
        self.parent = parent
        super().__init__(*args, **kwargs)


STATUSES_MAPS = {
    "Colis en préparation chez l'expéditeur": ParcelState.PLANNED,
    "Colis remis à Mondial Relay": ParcelState.IN_TRANSIT,
    "Colis en traitement sur le site logistique de destination.": ParcelState.IN_TRANSIT,
    "Colis disponible au Point Relais": ParcelState.ARRIVED,
    "Colis livré au destinataire": ParcelState.ARRIVED,
}


class TrackPage(ParentPage, JsonPage):
    ENCODING = "utf-8"

    class SubPage(SubPage, PartialHTMLPage):
        @property
        def content(self):
            return self.parent.doc["Message"].encode("utf-8")

        @method
        class get_parcel(ItemElement):
            klass = Parcel

            obj_id = Env("id")

            obj_info = CleanText("(//li[@class='validate'])[last()]")
            obj_status = Map(obj_info, STATUSES_MAPS, default=ParcelState.UNKNOWN)

            class obj_history(ListElement):
                item_xpath = "//div[@class='infos-account']"

                class date(ListElement):
                    def parse(self, el):
                        self.env["date"] = Regexp(
                            CleanText("./div/div/p/strong"), r"(\d{2}/\d{2}/\d{4})",
                        )(el)

                    item_xpath = ".//div[has-class('step-suivi') and not(./input)]"

                    class item(ItemElement):
                        klass = Event

                        obj_date = DateTime(
                            Format(
                                "%s %s",
                                Env("date"),
                                Regexp(
                                    CleanText("./div/p"),
                                    r"(\d{2}:\d{2})"
                                ),
                            ),
                            tzinfo="Europe/Paris", dayfirst=True, strict=False,
                        )
                        obj_activity = CleanText("./div/p[not(@class)]")
                        obj_location = Regexp(obj_activity, r"site logistique de ([^.]+)", default=NotAvailable)
