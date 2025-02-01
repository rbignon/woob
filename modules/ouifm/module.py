# -*- coding: utf-8 -*-

# Copyright(C) 2010-2014 Romain Bignon
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


from woob.browser.browsers import APIBrowser
from woob.capabilities.audiostream import BaseAudioStream
from woob.capabilities.collection import CapCollection
from woob.capabilities.radio import CapRadio, Radio
from woob.tools.backend import Module
from woob.tools.capabilities.streaminfo import StreamInfo
from woob.tools.misc import to_unicode


__all__ = ["OuiFMModule"]


class OuiFMModule(Module, CapRadio, CapCollection):
    NAME = "ouifm"
    MAINTAINER = "Romain Bignon"
    EMAIL = "romain@weboob.org"
    VERSION = "3.7"
    DESCRIPTION = "OÜI FM French radio"
    LICENSE = "AGPLv3+"
    BROWSER = APIBrowser

    _RADIOS = {
        "general": ("OUI FM", "OUI FM", 'http://stream.ouifm.fr/ouifm-high.mp3"', 160),
        "alternatif": ("OUI FM Alternatif", "OUI FM - Alternatif", "http://alternatif.stream.ouifm.fr/ouifm2.mp3", 128),
        "classicrock": (
            "OUI FM Classic Rock",
            "OUI FM - Classic Rock",
            "http://classicrock.stream.ouifm.fr/ouifm3.mp3",
            128,
        ),
        "bluesnrock": (
            "OUI FM Blues'n'Rock",
            "OUI FM - Blues'n'Rock",
            "http://bluesnrock.stream.ouifm.fr/ouifmbluesnrock-128.mp3",
            128,
        ),
        "rockinde": ("OUI FM Rock Indé", "OUI FM - Rock Indé", "http://rockinde.stream.ouifm.fr/ouifm5.mp3", 128),
        "ganja": ("OUI FM Ganja", "OUI FM - Ganja", "http://ganja.stream.ouifm.fr/ouifmganja-128.mp3", 128),
        "rock60s": ("OUI FM Rock 60's", "OUI FM - Rock 60's", "http://rock60s.stream.ouifm.fr/ouifmsixties.mp3", 128),
        "rock70s": ("OUI FM Rock 70's", "OUI FM - Rock 70's", "http://rock70s.stream.ouifm.fr/ouifmseventies.mp3", 128),
        "rock80s": ("OUI FM Rock 80's", "OUI FM - Rock 80's", "http://rock80s.stream.ouifm.fr/ouifmeighties.mp3", 128),
        "rock90s": ("OUI FM Rock 90's", "OUI FM - Rock 90's", "http://rock90s.stream.ouifm.fr/ouifmnineties.mp3", 128),
        "rock2000": (
            "OUI FM Rock 2000",
            "OUI FM - Rock 2000",
            "http://rock2000.stream.ouifm.fr/ouifmrock2000.mp3",
            128,
        ),
        "slowrock": (
            "OUI FM Les Slows du Rock",
            "OUI FM - Les Slows du Rock",
            "http://slowrock.stream.ouifm.fr/ouifmslowrock.mp3",
            128,
        ),
        "summertime": (
            "OUI FM Summertime",
            "OUI FM - Summertime",
            "http://summertime.stream.ouifm.fr/ouifmsummertime.mp3",
            128,
        ),
    }

    def iter_resources(self, objs, split_path):
        if Radio in objs:
            self._restrict_level(split_path)

            for id in self._RADIOS:
                yield self.get_radio(id)

    def iter_radios_search(self, pattern):
        for radio in self.iter_resources((Radio,), []):
            if pattern.lower() in radio.title.lower() or pattern.lower() in radio.description.lower():
                yield radio

    def get_current(self, radio):
        document = self.browser.request("http://www.ouifm.fr/onair.json")
        rad = ""
        if radio == "general":
            rad = "rock"
        else:
            rad = radio

        last = document[rad][0]

        artist = to_unicode(last.get("artist", "").strip())
        title = to_unicode(last.get("title", "").strip())
        return artist, title

    def get_radio(self, radio):
        if not isinstance(radio, Radio):
            radio = Radio(radio)

        if radio.id not in self._RADIOS:
            return None

        title, description, url, bitrate = self._RADIOS[radio.id]
        radio.title = title
        radio.description = description

        artist, title = self.get_current(radio.id)
        current = StreamInfo(0)
        current.who = artist
        current.what = title
        radio.current = current

        stream = BaseAudioStream(0)
        stream.bitrate = bitrate
        stream.format = "mp3"
        stream.title = "%skbits/s" % (stream.bitrate)
        stream.url = url
        radio.streams = [stream]
        return radio

    def fill_radio(self, radio, fields):
        if "current" in fields:
            if not radio.current:
                radio.current = StreamInfo(0)
            radio.current.who, radio.current.what = self.get_current(radio.id)
        return radio

    OBJECTS = {Radio: fill_radio}
