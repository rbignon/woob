# Copyright(C) 2014      Bezleputh
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

from collections import OrderedDict

from woob.capabilities.calendar import CATEGORIES, CapCalendarEvent
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import Value

from .browser import RazibusBrowser
from .calendar import RazibusCalendarEvent


__all__ = ["RazibusModule"]


class RazibusModule(Module, CapCalendarEvent):
    NAME = "razibus"
    DESCRIPTION = "site annonçant les évènements attendus par les punks a chiens"
    MAINTAINER = "Bezleputh"
    EMAIL = "carton_ben@yahoo.fr"
    LICENSE = "AGPLv3+"
    VERSION = "3.7"
    ASSOCIATED_CATEGORIES = [CATEGORIES.CONCERT]
    BROWSER = RazibusBrowser

    region_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    "": "-- Indifférent --",
                    "Alsace": "Alsace",
                    "Aquitaine": "Aquitaine",
                    "Auvergne": "Auvergne",
                    "Basse-Normandie": "Basse-Normandie",
                    "Bourgogne": "Bourgogne",
                    "Bretagne": "Bretagne",
                    "Centre": "Centre",
                    "Champagne-Ardenne": "Champagne-Ardenne",
                    "Franche-Comte": "Franche-Comté",
                    "Haute-Normandie": "Haute-Normandie",
                    "Ile-de-France": "Île-de-France",
                    "Languedoc-Roussillon": "Languedoc-Roussillon",
                    "Limousin": "Limousin",
                    "Lorraine": "Lorraine",
                    "Midi-Pyrenees": "Midi-Pyrénées",
                    "Nord-Pas-de-Calais": "Nord-Pas-de-Calais",
                    "Pays-de-la-Loire": "Pays de la Loire",
                    "Picardie": "Picardie",
                    "Poitou-Charentes": "Poitou-Charentes",
                    "PACA": "PACA",
                    "Rhone-Alpes": "Rhône-Alpes",
                    "Belgique": "Belgique",
                    "Suisse": "Suisse",
                }.items()
            )
        ]
    )

    CONFIG = BackendConfig(Value("region", label="Region", choices=region_choices, default=""))

    def create_default_browser(self):
        region = self.config["region"].get()
        return self.create_browser(region)

    def search_events(self, query):
        return self.browser.list_events(query.start_date, query.end_date, query.city, query.categories)

    def get_event(self, _id):
        return self.browser.get_event(_id)

    def list_events(self, date_from, date_to=None):
        return self.browser.list_events(date_from, date_to)

    def fill_obj(self, event, fields):
        return self.browser.get_event(event.id, event)

    OBJECTS = {RazibusCalendarEvent: fill_obj}
