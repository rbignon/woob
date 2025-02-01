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


from woob.browser import URL, PagesBrowser
from woob.browser.profiles import Firefox
from woob.capabilities.housing import HOUSE_TYPES, POSTS_TYPES, TypeNotSupported

from .pages import CitiesPage, HousingPage, PhonePage, SearchPage


class LogicimmoBrowser(PagesBrowser):
    BASEURL = "https://www.logic-immo.com/"
    PROFILE = Firefox()
    city = URL(r"asset/t9/getLocalityT9\.php\?site=fr&lang=fr&json=%22(?P<pattern>.*)%22", CitiesPage)
    search = URL(
        r"(?P<type>location-immobilier|vente-immobilier|recherche-colocation)-(?P<cities>.*)/options/(?P<options>.*)",
        SearchPage,
    )
    housing = URL(r"detail-(?P<_id>.*)\.htm", HousingPage)
    phone = URL(r"(?P<urlcontact>.*)", PhonePage)

    TYPES = {
        POSTS_TYPES.RENT: "location-immobilier",
        POSTS_TYPES.SALE: "vente-immobilier",
        POSTS_TYPES.SHARING: "recherche-colocation",
        POSTS_TYPES.FURNISHED_RENT: "location-immobilier",
        POSTS_TYPES.VIAGER: "vente-immobilier",
    }

    RET = {
        HOUSE_TYPES.HOUSE: "2",
        HOUSE_TYPES.APART: "1",
        HOUSE_TYPES.LAND: "3",
        HOUSE_TYPES.PARKING: "10",
        HOUSE_TYPES.OTHER: "14",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session.headers["X-Requested-With"] = "XMLHttpRequest"

    def get_cities(self, pattern):
        if pattern:
            return self.city.go(pattern=pattern).get_cities()

    def search_housings(self, type, cities, nb_rooms, area_min, area_max, cost_min, cost_max, house_types):
        if type not in self.TYPES:
            raise TypeNotSupported()

        options = []

        ret = []
        if type == POSTS_TYPES.VIAGER:
            ret = ["15"]
        else:
            for house_type in house_types:
                if house_type in self.RET:
                    ret.append(self.RET.get(house_type))

        if len(ret):
            options.append("groupprptypesids=%s" % ",".join(ret))

        if type == POSTS_TYPES.FURNISHED_RENT:
            options.append("searchoptions=4")

        options.append("pricemin=%s" % (cost_min if cost_min else "0"))

        if cost_max:
            options.append("pricemax=%s" % cost_max)

        options.append("areamin=%s" % (area_min if area_min else "0"))

        if area_max:
            options.append("areamax=%s" % area_max)

        if nb_rooms:
            if type == POSTS_TYPES.SHARING:
                options.append("nbbedrooms=%s" % ",".join([str(i) for i in range(nb_rooms, 7)]))
            else:
                options.append("nbrooms=%s" % ",".join([str(i) for i in range(nb_rooms, 7)]))

        self.search.go(type=self.TYPES.get(type, "location-immobilier"), cities=cities, options="/".join(options))

        if type == POSTS_TYPES.SHARING:
            return self.page.iter_sharing()

        return self.page.iter_housings(query_type=type)

    def get_housing(self, _id, housing=None):
        return self.housing.go(_id=_id).get_housing(obj=housing)

    def get_phone(self, _id):
        if _id.startswith("location") or _id.startswith("vente"):
            urlcontact, params = self.housing.stay_or_go(_id=_id).get_phone_url_datas()
            return self.phone.go(urlcontact=urlcontact, params=params).get_phone()
