# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from weboob.browser import AbstractBrowser, URL
from weboob.exceptions import BrowserIncorrectPassword, BrowserPasswordExpired

from .pages import LoginPage, LabelsPage, LoginConfirmPage


class NugerBrowser(AbstractBrowser):
    BASEURL = 'https://www.banque-nuger.fr'
    PARENT = 'creditdunord'

    # TODO: When the login change on creditdunord make sure to move this VK
    # on creditdunord.
    login = URL(
        r'$',
        r'/.*\?.*_pageLabel=page_erreur_connexion',
        r'/.*\?.*_pageLabel=reinitialisation_mot_de_passe',
        LoginPage
    )
    login_confirm = URL(r'/sec/vk/authent.json', LoginConfirmPage)
    labels_page = URL(r'/icd/zco/data/public-menu.json', LabelsPage)

    def do_login(self):
        self.login.go()
        self.page.login(self.username, self.password)

        assert self.login_confirm.is_here(), 'Should be on login confirmation page'

        if self.page.get_status() != 'ok':
            raise BrowserIncorrectPassword()
        elif self.page.get_reason() == 'chgt_mdp_oblig':
            # There is no message in the json return. There is just the code.
            raise BrowserPasswordExpired('Changement de mot de passe requis.')

        self.entrypage.go()
