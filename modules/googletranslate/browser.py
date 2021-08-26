# -*- coding: utf-8 -*-

# Copyright(C) 2012 Lucien Loiseau
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
from enum import Enum
import re

from woob.browser import PagesBrowser, URL
from woob.capabilities.base import NotAvailable, empty
from woob.tools.json import json
from urllib.parse import quote

from .pages import TranslatePage, SupportedLanguagesPage

__all__ = ['GoogleTranslateBrowser']


class GoogleRPC(Enum):
    AVdN8 = "AVdN8", "[text, source, to]", '[0][0][1]'
    MkEWBc = "MkEWBc", "[[text, source, to, True], [None]]", '[1][0][0][5][0][0]'

    def __new__(cls, action_name, parameter, result_handler):
        obj = object.__new__(cls)
        obj._value_ = action_name
        obj._parameter = parameter
        obj._result_handler = result_handler
        return obj

    @property
    def parameter(self):
        return self._parameter

    @property
    def result_handler(self):
        return self._result_handler


class GoogleTranslateBrowser(PagesBrowser):

    BASEURL = 'https://translate.google.com'

    translate_page = URL(
        fr'/_/TranslateWebserverUi/data/batchexecute\?rpcids=(?P<rpcid>({"|".join(GoogleRPC.__members__)}))',
        TranslatePage)
    languages_page = URL('https://ssl.gstatic.com/inputtools/js/ln/17/en.js', SupportedLanguagesPage)

    def get_supported_languages(self):
        return self.languages_page.go().get_supported_languages()

    def _gtranslate(self, source, to, text):
        for grpc in GoogleRPC:
            parameter = eval(grpc.parameter)
            escaped_parameter = json.dumps(parameter, separators=(',', ':'))

            rpc = [[[grpc.value, escaped_parameter, None, "generic"]]]
            espaced_rpc = json.dumps(rpc, separators=(',', ':'))

            res = self.translate_page.go(data="f.req={}&".format(quote(espaced_rpc)),
                                         rpcid=grpc.value).get_translation(grpc.result_handler)
            if not empty(res):
                return res

        return NotAvailable

    def translate(self, source, to, text):
        """
        translate 'text' from 'source' language to 'to' language
        """
        translation = []
        self.session.headers["Content-Type"] = "application/x-www-form-urlencoded;charset=utf-8"

        tokenized_text = re.split(r'([.!?]+)', " ".join([el.strip() for el in text.splitlines() if el]))
        _ = []
        for el in tokenized_text:
            if re.match(r'([.!?]+)', el) and len(_) > 0:
                _[-1] = f"{_[-1]}{el}"
            else:
                _.append(el.strip())

        for el in _:
            res = self._gtranslate(source, to, el)

            if not empty(res):
                translation.append(res)

        return " ".join(translation) if translation else NotAvailable
