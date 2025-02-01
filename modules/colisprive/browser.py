# -*- coding: utf-8 -*-

# Copyright(C) 2014 Florent Fourcot
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

from .pages import ErrorPage, TrackPage


class ColispriveBrowser(PagesBrowser):

    track_page = URL(r"https://www\.colisprive\.com/moncolis/pages/detailColis\.aspx\?numColis=(?P<id>.+)", TrackPage)
    error_page = URL("https://www.colisprive.fr", ErrorPage)

    def get_tracking_info(self, _id):
        return self.track_page.go(id=_id).get_info(_id)
