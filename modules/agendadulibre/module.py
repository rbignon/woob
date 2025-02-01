# -*- coding: utf-8 -*-

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

from .browser import AgendadulibreBrowser


__all__ = ["AgendadulibreModule"]


class AgendadulibreModule(Module, CapCalendarEvent):
    NAME = "agendadulibre"
    DESCRIPTION = "agendadulibre website"
    MAINTAINER = "Bezleputh"
    EMAIL = "carton_ben@yahoo.fr"
    LICENSE = "AGPLv3+"
    VERSION = "3.7"
    ASSOCIATED_CATEGORIES = [CATEGORIES.CONF]
    BROWSER = AgendadulibreBrowser

    region_choices = OrderedDict(
        [
            (k, "%s (%s)" % (v, k))
            for k, v in sorted(
                {
                    "https://www.agendadulibre.org": "--France--",
                    "https://www.agendadulibre.org#3": "Auvergne-Rhône-Alpes",
                    "https://www.agendadulibre.org#5": "Bourgogne-Franche-Comté",
                    "https://www.agendadulibre.org#6": "Bretagne",
                    "https://www.agendadulibre.org#7": "Centre-Val de Loire",
                    "https://www.agendadulibre.org#30": "Collectivité sui generis",
                    "https://www.agendadulibre.org#29": "Collectivités d'outre-mer",
                    "https://www.agendadulibre.org#9": "Corse",
                    "https://www.agendadulibre.org#1": "Grand Est",
                    "https://www.agendadulibre.org#23": "Guadeloupe",
                    "https://www.agendadulibre.org#24": "Guyane",
                    "https://www.agendadulibre.org#17": "Hauts-de-France",
                    "https://www.agendadulibre.org#12": "Île-de-France",
                    "https://www.agendadulibre.org#31": "Internet",
                    "https://www.agendadulibre.org#26": "La Réunion",
                    "https://www.agendadulibre.org#25": "Martinique",
                    "https://www.agendadulibre.org#28": "Mayotte",
                    "https://www.agendadulibre.org#4": "Normandie",
                    "https://www.agendadulibre.org#2": "Nouvelle-Aquitaine",
                    "https://www.agendadulibre.org#13": "Occitanie",
                    "https://www.agendadulibre.org#18": "Pays de la Loire",
                    "https://www.agendadulibre.org#21": "Provence-Alpes-Côte d'Azur",
                    "https://www.agendadulibre.be": "--Belgique--",
                    "https://www.agendadulibre.be#11": "Antwerpen",
                    "https://www.agendadulibre.be#10": "Brabant wallon",
                    "https://www.agendadulibre.be#9": "Bruxelles-Capitale",
                    "https://www.agendadulibre.be#8": "Hainaut",
                    "https://www.agendadulibre.be#7": "Liege",
                    "https://www.agendadulibre.be#6": "Limburg",
                    "https://www.agendadulibre.be#5": "Luxembourg",
                    "https://www.agendadulibre.be#4": "Namur",
                    "https://www.agendadulibre.be#3": "Oost-Vlaanderen",
                    "https://www.agendadulibre.be#2": "Vlaams-Brabant",
                    "https://www.agendadulibre.be#1": "West-Vlaanderen",
                    "https://www.agendadulibre.ch": "--Suisse--",
                    "https://www.agendadulibre.ch#15": "Appenzell Rhodes-Extérieures",
                    "https://www.agendadulibre.ch#16": "Appenzell Rhodes-Intérieures",
                    "https://www.agendadulibre.ch#19": "Argovie",
                    "https://www.agendadulibre.ch#13": "Bâle-Campagne",
                    "https://www.agendadulibre.ch#12": "Bâle-Ville",
                    "https://www.agendadulibre.ch#2": "Berne",
                    "https://www.agendadulibre.ch#10": "Fribourg",
                    "https://www.agendadulibre.ch#25": "Genève",
                    "https://www.agendadulibre.ch#8": "Glaris",
                    "https://www.agendadulibre.ch#18": "Grisons",
                    "https://www.agendadulibre.ch#26": "Jura",
                    "https://www.agendadulibre.ch#3": "Lucerne",
                    "https://www.agendadulibre.ch#24": "Neuchâtel",
                    "https://www.agendadulibre.ch#7": "Nidwald",
                    "https://www.agendadulibre.ch#6": "Obwald",
                    "https://www.agendadulibre.ch#17": "Saint-Gall",
                    "https://www.agendadulibre.ch#14": "Schaffhouse",
                    "https://www.agendadulibre.ch#5": "Schwytz",
                    "https://www.agendadulibre.ch#11": "Soleure",
                    "https://www.agendadulibre.ch#21": "Tessin",
                    "https://www.agendadulibre.ch#20": "Thurgovie",
                    "https://www.agendadulibre.ch#4": "Uri",
                    "https://www.agendadulibre.ch#23": "Valais",
                    "https://www.agendadulibre.ch#22": "Vaud",
                    "https://www.agendadulibre.ch#9": "Zoug",
                    "https://www.agendadulibre.ch#1": "Zurich",
                }.items()
            )
        ]
    )

    CONFIG = BackendConfig(Value("region", label="Region", choices=region_choices))

    def create_default_browser(self):
        choice = self.config["region"].get().split("#")
        selected_region = "" if len(choice) < 2 else choice[-1]
        return self.create_browser(website=choice[0], region=selected_region)

    def search_events(self, query):
        return self.browser.list_events(query.start_date, query.end_date, query.city, query.categories)

    def list_events(self, date_from, date_to=None):
        return self.browser.list_events(date_from, date_to)

    def get_event(self, event_id):
        return self.browser.get_event(event_id)

    def fill_obj(self, event, fields):
        event = self.browser.get_event(event.id, event)
        choice = self.config["region"].get().split("#")
        selected_region = "" if len(choice) < 2 else choice[-1]
        if selected_region == "23":
            event.timezone = "America/Guadeloupe"
        elif selected_region == "24":
            event.timezone = "America/Guyana"
        elif selected_region == "26":
            event.timezone = "Indian/Reunion"
        elif selected_region == "25":
            event.timezone = "America/Martinique"
        else:
            event.timezone = "Europe/Paris"
        return event

    OBJECTS = {AgendadulibreBrowser: fill_obj}
