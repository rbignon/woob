# Copyright(C) 2013      Vincent A
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

import re
from datetime import datetime, time

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import Field
from woob.browser.pages import JsonPage
from woob.capabilities.base import NotAvailable
from woob.capabilities.calendar import CATEGORIES, STATUS, TRANSP, BaseCalendarEvent


class NoEvent(Exception):
    pass


class EventItem(ItemElement):
    klass = BaseCalendarEvent

    obj_id = Dict("id")
    obj_city = Dict("ville")
    obj_category = CATEGORIES.CONCERT

    obj_timezone = "Europe/Paris"

    def obj_start_date(self):
        return datetime.fromtimestamp(int(self.el["datetimestamp"]))

    def obj_end_date(self):
        return datetime.combine(self.obj_start_date().date(), time.max)

    def obj_summary(self):
        t = " + ".join(g["NomGroupe"] for g in self.el["groupes"])
        if int(self.el["Guest"]):
            t += " + GUEST(S)"
        return t

    def obj_description(self):
        parts = []
        for g in self.el["groupes"]:
            if "WebOfficielGroupe" in g:
                parts.append("{} ({}): {}".format(g["NomGroupe"], g["StyleMusicalGroupe"], g["WebOfficielGroupe"]))
            else:
                parts.append("{} ({})".format(g["NomGroupe"], g["StyleMusicalGroupe"]))
        if int(self.el["Guest"]):
            parts.append("GUEST(S)")
        return "\n".join(parts)

    def obj__flyer(self):
        img = self.el["flyer"]
        if img:
            return "http://sueurdemetal.com/images/flyers/" + img
        else:
            return NotAvailable

    def obj_url(self):
        slug = re.sub("[^a-z]", "", self.el["groupes"][0]["NomGroupe"], flags=re.I).lower()
        return "http://www.sueurdemetal.com/detail-concert/{}-{}".format(slug, Field("id")(self))

    def obj_status(self):
        statuses = {
            "0": STATUS.CONFIRMED,
            "2": STATUS.CANCELLED,
        }
        return statuses.get(self.el["etat"])

    obj_transp = TRANSP.OPAQUE


class ConcertListPage(JsonPage):
    @method
    class iter_concerts(DictElement):
        item_xpath = "results/collection1"

        class item(EventItem):
            pass


class ConcertPage(JsonPage):
    @method
    class get_concert(EventItem):
        def parse(self, el):
            try:
                self.el = self.el["results"]["collection1"][0]
            except IndexError:
                raise NoEvent()

        def obj_price(self):
            return float(re.match(r"[\d.]+", self.el["prix"]).group(0))

        def obj_location(self):
            return "{}, {}".format(self.el["salle"], self.el["adresse"])
