# -*- coding: utf-8 -*-

# Copyright(C) 2021 Vincent A
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

# flake8: compatible

import re

from woob.browser import URL, PagesBrowser

from .pages import FormPage, TrackPage


class MondialrelayBrowser(PagesBrowser):
    BASEURL = "https://www.mondialrelay.fr/"

    track = URL(r"/_mvc/fr-FR/SuiviExpedition/RechercherJsonResponsive", TrackPage)
    form = URL(r"/suivi-de-colis", FormPage)

    def __init__(self, postal_code, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.postal_code = postal_code

    def get_parcel_tracking(self, id):
        match = re.fullmatch(r"(?P<number>\d{8,12})(?P<sep>[/._-])(?P<postal_code>\d{5})", id)
        if match:
            number, sep, postal_code = match["number"], match["sep"], match["postal_code"]
        else:
            assert self.postal_code
            assert id.isdigit()
            number, sep, postal_code = id, ".", self.postal_code
            id = f"{number}{sep}{postal_code}"

        self.form.go()
        self.page.submit(number, postal_code)
        return self.page.sub_page.get_parcel(id=id)
