# Copyright(C) 2013      Romain Bignon
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

from .pages import TrackPage


__all__ = ["ChronopostBrowser"]


class ChronopostBrowser(PagesBrowser):
    BASEURL = "https://www.chronopost.fr"
    track = URL(r"/tracking-no-cms/suivi-colis\?listeNumerosLT=(?P<id>\w+)&langue=fr", TrackPage)

    def get_tracking_info(self, _id):
        self.track.go(
            id=_id, headers={"Referer": "https://www.chronopost.fr/tracking-no-cms/suivi-page?listeNumerosLT=%s" % id}
        )
        return self.page.get_parcel()
