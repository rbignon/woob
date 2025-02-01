# -*- coding: utf-8 -*-

# Copyright(C) 2017      Phyks (Lucas Verney)
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

from itertools import chain

from selenium import webdriver

from woob.browser import URL, PagesBrowser
from woob.browser.exceptions import HTTPNotFound
from woob.browser.selenium import SeleniumBrowser, SubSeleniumMixin
from woob.capabilities.base import NotAvailable, empty
from woob.capabilities.housing import HOUSE_TYPES, POSTS_TYPES

from .constants import AVAILABLE_TYPES, BASE_URL, QUERY_HOUSE_TYPES, QUERY_TYPES
from .pages import AgencyPage, CitiesPage, HousingPage, IndexPage, SearchResultsPage


class FonciaSeleniumBrowser(SeleniumBrowser):
    BASEURL = BASE_URL
    HEADLESS = True  # Always change to True for prod

    DRIVER = webdriver.Chrome
    WINDOW_SIZE = (1920, 1080)

    home = URL("/$", IndexPage)

    def __init__(self, config, *args, **kwargs):
        super(FonciaSeleniumBrowser, self).__init__(*args, **kwargs)

    def _build_options(self, preferences):
        # MyFoncia login use a library called FingerprintJS
        # It can assert whether or not the user is a bot
        # To successfully pass the login, we have to
        options = super(FonciaSeleniumBrowser, self)._build_options(preferences)
        # Hide the fact that the navigator is controlled by webdriver
        options.add_argument("--disable-blink-features=AutomationControlled")
        # Hardcode an User Agent so we don't expose Chrome is in headless mode
        options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64; rv:78.0) Gecko/20100101 Firefox/78.0")

        return options

    def go_home(self):
        self.home.go()


class FonciaBrowser(PagesBrowser, SubSeleniumMixin):
    BASEURL = "https://fnc-api.prod.fonciatech.net"
    SELENIUM_BROWSER = FonciaSeleniumBrowser

    cities = URL(r"/geo/localities/search", CitiesPage)
    search = URL(r"/annonces/annonces/search", SearchResultsPage)
    housing = URL(r"/annonces/annonces/(?P<housing_id>.+)", HousingPage)
    agency = URL(r"/agences/agences/(?P<agency_id>\d+)", AgencyPage)

    def __init__(self, *args, **kwargs):
        self.config = None
        super(FonciaBrowser, self).__init__(*args, **kwargs)
        sub_browser = self.create_selenium_browser()
        try:
            if self.selenium_state and hasattr(sub_browser, "load_state"):
                sub_browser.load_state(self.selenium_state)
            sub_browser.go_home()
            self.load_selenium_session(sub_browser)
        finally:
            try:
                if hasattr(sub_browser, "dump_state"):
                    self.selenium_state = sub_browser.dump_state()
            finally:
                sub_browser.deinit()

    def get_cities(self, pattern):
        data = {"page": 1, "query": pattern, "size": 20}

        return self.cities.go(json=data).iter_cities()

    def search_housings(self, query, cities):
        def fill_min_max(data_dict, key, min_value=None, max_value=None):
            if min_value or max_value:
                data_dict[key] = {}

                if not empty(min_value):
                    data_dict[key]["min"] = min_value

                if not empty(max_value):
                    data_dict[key]["max"] = max_value

        if QUERY_TYPES[query.type] == POSTS_TYPES.FURNISHED_RENT:
            if query.house_types != HOUSE_TYPES.APART:
                return
            else:
                types_biens = AVAILABLE_TYPES[POSTS_TYPES.FURNISHED_RENT]
        elif HOUSE_TYPES.UNKNOWN in query.house_types:
            types_biens = AVAILABLE_TYPES[query.type]
        else:
            types_biens = list(chain(*[QUERY_HOUSE_TYPES[_] for _ in query.house_types]))
            types_biens = [_ for _ in types_biens if _ in AVAILABLE_TYPES[query.type]]

        data = {
            "type": QUERY_TYPES[query.type],
            "filters": {"localities": {"slugs": cities}, "typesBien": types_biens},
            "expandNearby": True,
            "size": 15,
            "page": 1,
        }

        fill_min_max(data["filters"], "surface", query.area_min, query.area_max)
        fill_min_max(data["filters"], "prix", query.cost_min, query.cost_max)
        fill_min_max(data["filters"], "nbPiece", query.nb_rooms)

        return self.search.go(json=data).iter_housings(data=data)

    def get_housing(self, housing_id, housing=None):
        housing = self.housing.go(housing_id=housing_id).get_housing(obj=housing)
        housing.phone = self.get_phone(housing_id)
        return housing

    def get_phone(self, housing_id):
        agency_id = self.housing.stay_or_go(housing_id=housing_id).get_agency_id()
        try:
            return self.agency.go(agency_id=agency_id).get_phone()
        except HTTPNotFound:
            return NotAvailable
