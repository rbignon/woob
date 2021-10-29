# -*- coding: utf-8 -*-

# Copyright(C) 2017      Phyks (Lucas Verney)
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from selenium import webdriver

from woob.browser import PagesBrowser, need_login, URL
from woob.browser.selenium import SeleniumBrowser, SubSeleniumMixin
from woob.exceptions import BrowserIncorrectPassword, BrowserUnavailable

from .pages import LoginPage, MyPropertyPage, DocumentsPage, FeesPage


class MyFonciaSeleniumBrowser(SeleniumBrowser):
    BASEURL = 'https://myfoncia.fr'
    HEADLESS = True

    DRIVER = webdriver.Chrome
    WINDOW_SIZE = (1920, 1080)

    login = URL(r'/login', LoginPage)

    def __init__(self, config, *args, **kwargs):
        self.username = config['login'].get()
        self.password = config['password'].get()
        super(MyFonciaSeleniumBrowser, self).__init__(*args, **kwargs)

    def _build_options(self, preferences):
        # MyFoncia login use a library called FingerprintJS
        # It can assert whether or not the user is a bot
        # To successfully pass the login, we have to
        options = super(MyFonciaSeleniumBrowser, self)._build_options(preferences)
        # Hide the fact that the navigator is controlled by webdriver
        options.add_argument('--disable-blink-features=AutomationControlled')
        # Hardcode an User Agent so we don't expose Chrome is in headless mode
        options.add_argument('user-agent=Mozilla/5.0 (X11; Linux x86_64; rv:78.0) Gecko/20100101 Firefox/78.0')

        return options

    def do_login(self):
        self.login.go()
        self.page.do_login(self.username, self.password)
        if self.login.is_here():
            msg = self.page.get_error_msg()
            if 'Service momentanément indisponible' in msg:
                raise BrowserUnavailable()
            # Votre e-mail, votre identifiant ou votre mot de passe est incorrect.
            elif 'mot de passe est incorrect' in msg:
                raise BrowserIncorrectPassword()
            raise AssertionError('Unhandled error message at login step: %s', msg)


class MyFonciaBrowser(PagesBrowser, SubSeleniumMixin):
    BASEURL = 'https://myfoncia.fr'

    SELENIUM_BROWSER = MyFonciaSeleniumBrowser

    my_property = URL(r'/espace-client/espace-de-gestion/mon-bien', MyPropertyPage)
    documents = URL(
        r'/espace-client/espace-de-gestion/mes-documents/(?P<subscription_id>.+)/(?P<letter>[A-Z])',
        DocumentsPage
    )
    fees = URL(
        r'/espace-client/espace-de-gestion/mes-charges/(?P<subscription_id>.+)',
        FeesPage
    )

    def __init__(self, config, *args, **kwargs):
        self.config = config
        super(MyFonciaBrowser, self).__init__(*args, **kwargs)

    @need_login
    def get_subscriptions(self):
        self.my_property.go()
        return self.page.get_subscriptions()

    @need_login
    def iter_documents(self, subscription):
        self.documents.go(subscription_id=subscription, letter=subscription[-1])
        for document in self.page.iter_documents(subscription_id=subscription):
            yield document

        self.fees.go(subscription_id=subscription)
        for fee in self.page.iter_fees():
            yield fee
