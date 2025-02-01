# -*- coding: utf-8 -*-

# Copyright(C) 2013      Bezleputh
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

from woob.browser import URL, PagesBrowser
from woob.browser.profiles import Firefox

from .pages import EventPage, ProgramPage


__all__ = ["HybrideBrowser"]


class HybrideBrowser(PagesBrowser):
    PROFILE = Firefox()
    BASEURL = "https://www.lhybride.org/"

    program_page = URL("programmation/a-venir.html", ProgramPage)
    event_page = URL("programmation/item/(?P<_id>.*)", EventPage)

    def list_events(self, date_from, date_to=None, city=None, categories=None):
        return self.program_page.go().list_events(
            date_from=date_from, date_to=date_to, city=city, categories=categories
        )

    def get_event(self, _id, event=None):
        return self.event_page.go(_id=_id).get_event(obj=event)
