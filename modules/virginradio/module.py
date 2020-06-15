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
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.


from weboob.capabilities.radio import CapRadio, Radio
from weboob.capabilities.audiostream import BaseAudioStream
from weboob.capabilities.collection import CapCollection
from weboob.tools.backend import Module
from .browser import VirginBrowser

__all__ = ['VirginRadioModule']


class VirginRadioModule(Module, CapRadio, CapCollection):
    NAME = 'virginradio'
    MAINTAINER = u'Johann Broudin'
    EMAIL = 'Johann.Broudin@6-8.fr'
    VERSION = '2.1'
    DESCRIPTION = u'VirginRadio french radio'
    LICENSE = 'AGPLv3+'
    BROWSER = VirginBrowser

    def get_radio(self, radio):
        if not isinstance(radio, Radio):
            radio = Radio(radio)

        r = self.browser.radio(radio.id)

        if r is None:
            return None

        radio.title = r['title']

        radio.description = self.browser.description(r)

        stream_hls = BaseAudioStream(0)
        stream_hls.url = r['hls_source']
        stream_hls.bitrate = 135
        stream_hls.format = u'aac'
        stream_hls.title = u'%s %skbits/s' % (stream_hls.format, stream_hls.bitrate)

        stream = BaseAudioStream(0)
        stream.url = r['source']
        stream.bitrate = 128
        stream.format = u'mp3'
        stream.title = u'%s %skbits/s' % (stream.format, stream.bitrate)

        radio.streams = [stream_hls, stream]
        radio.current = self.browser.current(r)

        return radio

    def iter_resources(self, objs, split_path):
        if Radio in objs:
            self._restrict_level(split_path)

            radios = self.browser.radios()

            for id in radios:
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
