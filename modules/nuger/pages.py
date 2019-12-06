# -*- coding: utf-8 -*-

# Copyright(C) 2012-2019  Budget Insight

from weboob.browser.pages import AbstractPage, JsonPage
from weboob.browser.filters.json import Dict


class LoginPage(AbstractPage):
    PARENT = 'creditdunord'
    PARENT_URL = 'login'

    def login(self, username, password):
        res = self.browser.open('/sec/vk/gen_crypto.json').json()
        crypto = res['donnees']['crypto']
        grid = res['donnees']['grid']

        vk = self.VIRTUALKEYBOARD(self.browser, crypto, grid)

        data = {
            'user_id': username,
            'vk_op': 'auth',
            'codsec': vk.get_string_code(password),
            'cryptocvcs': crypto,
        }
        self.browser.location('/sec/vk/authent.json', data=data)


class LabelsPage(AbstractPage):
    PARENT = 'creditdunord'
    PARENT_URL = 'labels_page'


class LoginConfirmPage(JsonPage):
    def get_status(self):
        return Dict('commun/statut')(self.doc)
