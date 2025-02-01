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

from .pages import AdvertPage, SearchPage


__all__ = ["IndeedBrowser"]


class IndeedBrowser(PagesBrowser):

    BASEURL = "https://www.indeed.fr"

    search_page = URL("/emplois(?P<parameters>.*)", SearchPage)
    advert_page = URL("/cmp/(?P<company>.*)/jobs/(?P<title>.*)-(?P<nb>.*)", AdvertPage)

    def search_job(self, metier="", contrat="", limit_date="", radius="", place=""):
        params = "?q={}&limit=10&sort=date&st=employer&sr=directhire&jt={}&fromage={}&radius={}".format(
            metier.replace(" ", "+"),
            contrat,
            limit_date,
            radius,
        )
        if place:
            params = f"{params}&l={place}"
        self.search_page.go(parameters=params)
        assert self.search_page.is_here(parameters=params)
        return self.page.iter_job_adverts()

    def get_job_advert(self, _id, advert):
        splitted_id = _id.split("#")
        return self.advert_page.go(nb=splitted_id[0], title=splitted_id[1], company=splitted_id[2]).get_job_advert(
            obj=advert
        )
