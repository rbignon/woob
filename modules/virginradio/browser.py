# -*- coding: utf-8 -*-

# Copyright(C) 2020 Johann Broudin
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distribute in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from weboob.tools.capabilities.streaminfo import StreamInfo
from weboob.browser import Browser

from . import parser


class VirginBrowser(Browser):
    _RADIOS_URL = 'https://www.virginradio.fr/desktop/js/all.min.js'
    _PROGRAM_URL = 'https://www.virginradio.fr/calendar/api/current.json/argv/calendar_type/emission/origine_flags/virginradio/get_current_foreign_type/TRUE'
    _INFO_URL = 'https://www.virginradio.fr/radio/api/get_current_event/?id_radio=%s'
    _WEBRADIOS_URL = 'https://www.virginradio.fr/webradios/'

    def __init__(self, *args, **kwargs):
        super(VirginBrowser, self).__init__(*args, **kwargs)
        self._radios = {}

    def radios(self):
        webradios = self.open(self._WEBRADIOS_URL)
        radiosjs = self.open(self._RADIOS_URL)
        radios = parser.radios(webradios, radiosjs)
        self._radios = radios
        return radios

    def radio(self, radio):
        if not self._radios:
            self.radios()

        if radio not in self._radios:
            return None

        return self._radios[radio]

    def current(self, radio):
        r = self.open(self._INFO_URL % (radio['radio_id']))
        who, what = parser.current(r)
        current = StreamInfo(0)
        current.who = who
        current.what = what
        return current

    def description(self, radio):
        description = radio['title']
        if radio['name'] == 'live':
            r = self.open(self._PROGRAM_URL)
            description = parser.description(r)

        return description
