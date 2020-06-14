# -*- coding: utf-8 -*-

# Copyright(C) 2014 Johann Broudin
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.


from weboob.capabilities.radio import CapRadio, Radio
from weboob.capabilities.audiostream import BaseAudioStream
from weboob.tools.capabilities.streaminfo import StreamInfo
from weboob.capabilities.collection import CapCollection
from weboob.tools.backend import Module
from weboob.browser import Browser
import re
from lxml import html


__all__ = ['VirginRadioModule']


class VirginRadioModule(Module, CapRadio, CapCollection):
    NAME = 'virginradio'
    MAINTAINER = u'Johann Broudin'
    EMAIL = 'Johann.Broudin@6-8.fr'
    VERSION = '2.1'
    DESCRIPTION = u'VirginRadio french radio'
    LICENSE = 'AGPLv3+'
    BROWSER = Browser

    _RADIOS_URL = 'https://www.virginradio.fr/desktop/js/all.min.js'
    _RADIOS_RE = (
            r'{id:(?P<id>\d+),'
            r'id_radio:(?P<id_radio>\d+),'
            r'type:"[^"]*",'
            r'name:"(?P<name>[^"]*)",'
            r'hls_source:"(?P<hls_source>[^"]*)",'
            r'source:"(?P<source>[^"]*)"'
            )

    _PROGRAM_URL = 'https://www.virginradio.fr/calendar/api/current.json/argv/calendar_type/emission/origine_flags/virginradio/get_current_foreign_type/TRUE'
    _INFO_URL = 'https://www.virginradio.fr/radio/api/get_current_event/?id_radio=%s'

    _WEBRADIOS_URL = 'https://www.virginradio.fr/webradios/'
    _XPATH_RADIO_NAME = '//ul/li[@class="brick"]/div/div[@data-id="%s"]/ancestor::li/div/h3/text()'

    _RADIOS = {}

    def get_radio(self, radio):
        self.get_radios()
        if not isinstance(radio, Radio):
            radio = Radio(radio)

        if radio.id not in self._RADIOS:
            return None

        radio.title = self._RADIOS[radio.id]['title']
        radio.description = self._RADIOS[radio.id]['title']

        if radio.id == 'live':
            r = self.browser.open(self._PROGRAM_URL)
            info = r.json()['root_tab']['events'][0]
            radio.description = "%s - %s" % (info['title'], info['tab_foreign_type']['resum'])

        stream_hls = BaseAudioStream(0)
        stream_hls.url = self._RADIOS[radio.id]['hls_source']
        stream_hls.bitrate = 128
        stream_hls.format=u'aac'

        stream = BaseAudioStream(0)
        stream.url = self._RADIOS[radio.id]['source']
        stream.bitrate = 128
        stream.format=u'mp3'

        current = StreamInfo(0)
        current.who = ''
        current.what = ''

        r = self.browser.open(self._INFO_URL % (self._RADIOS[radio.id]['radio_id']))
        info = r.json()['root_tab']['event']
        if len(info) > 0:
            current.who = info[0]['artist']
            current.what = info[0]['title']
        radio.streams = [stream_hls, stream]
        radio.current = current
        return radio

    def get_radios(self):
        webradios = self.browser.open(self._WEBRADIOS_URL)
        tree = html.fromstring(webradios.content)

        if not self._RADIOS:
            r = self.browser.open(self._RADIOS_URL)
            for m in re.finditer(self._RADIOS_RE, r.text):
                self._RADIOS[m.group('name')] = {
                        'radio_id': m.group('id_radio'),
                        'name': m.group('name'),
                        'hls_source': m.group('hls_source'),
                        'source': m.group('source'),
                        'title': tree.xpath(self._XPATH_RADIO_NAME % (m.group('id_radio')))[0] }

    def iter_resources(self, objs, split_path):
        if Radio in objs:
            self._restrict_level(split_path)

            self.get_radios()

            for id in self._RADIOS:
                yield self.get_radio(id)

    def iter_radios_search(self, pattern):
        for radio in self.iter_resources((Radio, ), []):
            if pattern.lower() in radio.title.lower() or pattern.lower() in radio.description.lower():
                yield radio

    def fill_radio(self, radio, fields):
        if 'current' in fields:
            if not radio.current:
                radio = self.get_radio(radio.id)
        return radio

    OBJECTS = {Radio: fill_radio}
