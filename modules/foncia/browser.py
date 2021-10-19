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

from __future__ import unicode_literals

from selenium import webdriver

from woob.browser.selenium import SeleniumBrowser, SubSeleniumMixin
from woob.browser import PagesBrowser, URL

from .constants import QUERY_TYPES
from .pages import CitiesPage, HousingPage, SearchPage, SearchResultsPage, IndexPage


class FonciaSeleniumBrowser(SeleniumBrowser):
    BASEURL = 'https://fr.foncia.com'
    HEADLESS = True  # Always change to True for prod

    DRIVER = webdriver.Chrome
    WINDOW_SIZE = (1920, 1080)

    home = URL('/$', IndexPage)

    def __init__(self, config, *args, **kwargs):
        super(FonciaSeleniumBrowser, self).__init__(*args, **kwargs)

    def _build_options(self, preferences):
        # MyFoncia login use a library called FingerprintJS
        # It can assert whether or not the user is a bot
        # To successfully pass the login, we have to
        options = super(FonciaSeleniumBrowser, self)._build_options(preferences)
        # Hide the fact that the navigator is controlled by webdriver
        options.add_argument('--disable-blink-features=AutomationControlled')
        # Hardcode an User Agent so we don't expose Chrome is in headless mode
        options.add_argument('user-agent=Mozilla/5.0 (X11; Linux x86_64; rv:78.0) Gecko/20100101 Firefox/78.0')

        return options

    def go_home(self):
        self.home.go()


class FonciaBrowser(PagesBrowser, SubSeleniumMixin):
    BASEURL = 'https://fr.foncia.com'

    SELENIUM_BROWSER = FonciaSeleniumBrowser

    cities = URL(r'/recherche/autocomplete\?term=(?P<term>.+)', CitiesPage)
    housing = URL(r'/(?P<type>[^/]+)/.*\d+.htm', HousingPage)
    search_results = URL(r'/(?P<type>[^/]+)/.*', SearchResultsPage)
    search = URL(r'/(?P<type>.+)', SearchPage)

    def __init__(self, *args, **kwargs):
        self.config = None
        super(FonciaBrowser, self).__init__(*args, **kwargs)
        sub_browser = self.create_selenium_browser()
        try:
            if self.selenium_state and hasattr(sub_browser, 'load_state'):
                sub_browser.load_state(self.selenium_state)
            sub_browser.go_home()
            self.load_selenium_session(sub_browser)
        finally:
            try:
                if hasattr(sub_browser, 'dump_state'):
                    self.selenium_state = sub_browser.dump_state()
            finally:
                sub_browser.deinit()

    def get_cities(self, pattern):
        """
        Get cities matching a given pattern.
        """
        return self.cities.open(term=pattern).iter_cities()

    def search_housings(self, query, cities):
        """
        Search for housings matching given query.
        """
        try:
            query_type = QUERY_TYPES[query.type]
        except KeyError:
            return []

        self.search.go(type=query_type).do_search(query, cities)
        return self.page.iter_housings(query_type=query.type)

    def get_housing(self, _id):
        """
        Get specific housing.
        """
        query_type, _id = _id.split(':')
        self.search.go(type=query_type).find_housing(query_type, _id)
        return self.page.get_housing()
