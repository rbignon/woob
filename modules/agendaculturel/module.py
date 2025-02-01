# Copyright(C) 2015      Bezleputh
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


from woob.capabilities.calendar import CATEGORIES, CapCalendarEvent
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import Value

from .browser import AgendaculturelBrowser
from .calendar import AgendaculturelEvent


__all__ = ["AgendaculturelModule"]


class AgendaculturelModule(Module, CapCalendarEvent):
    NAME = "agendaculturel"
    DESCRIPTION = "agendaculturel website"
    MAINTAINER = "Bezleputh"
    EMAIL = "carton_ben@yahoo.fr"
    LICENSE = "AGPLv3+"
    VERSION = "3.7"
    ASSOCIATED_CATEGORIES = [CATEGORIES.CONCERT, CATEGORIES.THEATRE, CATEGORIES.EXPO, CATEGORIES.AUTRE, CATEGORIES.FEST]
    BROWSER = AgendaculturelBrowser

    CONFIG = BackendConfig(Value("place", label="Default place"))

    def create_default_browser(self):
        return self.create_browser(self.config["place"].get())

    def get_event(self, _id):
        return self.browser.get_event(_id)

    def list_events(self, date_from, date_to=None):
        default_place = self.config["place"].get()
        return self.browser.list_events(default_place, date_from, date_to)

    def search_events(self, query):
        if self.has_matching_categories(query):
            return self.browser.list_events(query.city, query.start_date, query.end_date, query.categories)

    def fill_obj(self, event, fields):
        return self.browser.get_event(event.id, event)

    OBJECTS = {AgendaculturelEvent: fill_obj}
