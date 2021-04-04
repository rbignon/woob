# -*- coding: utf-8 -*-

# Copyright(C) 2020      Budget Insight

# flake8: compatible

from woob.browser.pages import AbstractPage


class LoginPage(AbstractPage):
    PARENT = 'caissedepargne'
    PARENT_URL = 'login'
    BROWSER_ATTR = 'package.browser.CaisseEpargne'


class NewLoginPage(AbstractPage):
    PARENT = 'caissedepargne'
    PARENT_URL = 'new_login'
    BROWSER_ATTR = 'package.browser.CaisseEpargne'


class JsFilePage(AbstractPage):
    PARENT = 'caissedepargne'
    PARENT_URL = 'js_file'
    BROWSER_ATTR = 'package.browser.CaisseEpargne'


class ConfigPage(AbstractPage):
    PARENT = 'caissedepargne'
    PARENT_URL = 'config_page'
    BROWSER_ATTR = 'package.browser.CaisseEpargne'
