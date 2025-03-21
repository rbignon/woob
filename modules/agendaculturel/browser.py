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

import re
from urllib.parse import urlparse

from woob.browser import URL, PagesBrowser

from .pages import BasePage


class AgendaculturelBrowser(PagesBrowser):
    BASEURL = ""

    base = URL(
        "https://www.agendaculturel.fr/search_bw",
        r"https://(?P<region>\d{2})\.agendaculturel\.fr/(?P<_id>.*)\.html",
        r"https://\d{2}\.agendaculturel\.fr/.*",
        BasePage,
    )

    def __init__(self, place, *args, **kwargs):
        self.default_place = place
        PagesBrowser.__init__(self, *args, **kwargs)

    def set_base_url(self, place):
        if not place:
            place = self.default_place
        self.base.go(data={"query": place})
        parsed_uri = urlparse(self.page.url)
        self.BASEURL = "{uri.scheme}://{uri.netloc}/".format(uri=parsed_uri)

    def list_events(self, place, date_from, date_to, categories=None):
        self.set_base_url(place)
        query_date_from = date_from.strftime("%Y%m")
        self.page.search_events(query_date_from)
        region = re.match(r"https://(\d{2})\.agendaculturel\.fr/.*", self.page.url).group(1)
        return self.page.list_events(region=region, date_from=date_from, date_to=date_to, categories=categories)

    def get_event(self, id, event=None):
        splitted_id = id.split(".")
        region = splitted_id[0]
        _id = splitted_id[1]
        return self.base.go(_id=_id, region=region).get_event(obj=event)
