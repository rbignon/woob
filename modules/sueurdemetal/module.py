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


from woob.capabilities.calendar import CATEGORIES, BaseCalendarEvent, CapCalendarEvent, Query
from woob.tools.backend import Module

from .browser import SueurDeMetalBrowser


__all__ = ["SueurDeMetalModule"]


class SueurDeMetalModule(Module, CapCalendarEvent):
    NAME = "sueurdemetal"
    DESCRIPTION = "SueurDeMetal French concerts list website"
    MAINTAINER = "Vincent A"
    EMAIL = "dev@indigo.re"
    LICENSE = "AGPLv3+"
    VERSION = "3.7"

    BROWSER = SueurDeMetalBrowser

    ASSOCIATED_CATEGORIES = [CATEGORIES.CONCERT]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.cities = {}

    def search_events(self, query):
        if not self.has_matching_categories(query):
            return

        for ev in self.browser.search_city(query.city or "00"):
            if query.start_date and ev.start_date < query.start_date:
                continue
            if query.end_date and ev.start_date > query.end_date:
                continue
            yield ev

    def list_events(self, date_from, date_to=None):
        q = Query()
        q.start_date = date_from
        q.end_date = date_to
        return self.search_events(q)

    def get_event(self, id):
        return self.browser.get_concert(id)

    def fill_concert(self, obj, fields):
        if set(fields) & {"location", "price"}:
            new = self.get_event(obj.id)
            for f in fields:
                setattr(obj, f, getattr(new, f))
        return obj

    OBJECTS = {BaseCalendarEvent: fill_concert}
