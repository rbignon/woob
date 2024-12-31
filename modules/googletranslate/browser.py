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

import re
from urllib.parse import quote

from woob.browser import URL, PagesBrowser
from woob.capabilities.base import NotAvailable, empty
from woob.tools.json import json

from .pages import SupportedLanguagesPage, TranslatePage


__all__ = ['GoogleTranslateBrowser']


class RPCS:
    class AVdN8:
        name = "AVdN8"

        @staticmethod
        def parameter(text, source, to):
            return [text, source, to]

        @staticmethod
        def result_handler(d):
            return d[0][0][1]

    class MkEWBc:
        name = "MkEWBc"

        @staticmethod
        def parameter(text, source, to):
            return [[text, source, to, True], [None]]

        @staticmethod
        def result_handler(d):
            return d[1][0][0][5][0][0]


    values = [AVdN8, MkEWBc]
    names = [cls.name for cls in values]


class GoogleTranslateBrowser(PagesBrowser):

    BASEURL = 'https://translate.google.com'

    translate_page = URL(
        fr'/_/TranslateWebserverUi/data/batchexecute\?rpcids=(?P<rpcid>({"|".join(RPCS.names)}))',
        TranslatePage)
    languages_page = URL('https://ssl.gstatic.com/inputtools/js/ln/17/en.js', SupportedLanguagesPage)

    def get_supported_languages(self):
        return self.languages_page.go().get_supported_languages()

    def _gtranslate(self, source, to, text):
        for grpc in RPCS.values:
            parameter = grpc.parameter(text, source, to)
            escaped_parameter = json.dumps(parameter, separators=(',', ':'))

            rpc = [[[grpc.name, escaped_parameter, None, "generic"]]]
            espaced_rpc = json.dumps(rpc, separators=(',', ':'))

            self.translate_page.go(data="f.req={}&".format(quote(espaced_rpc)), rpcid=grpc.name)
            res = self.page.get_translation(grpc.result_handler)
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
