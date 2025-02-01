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
"backend for http://translate.google.com"

from woob.capabilities.base import empty
from woob.capabilities.translate import CapTranslate, LanguageNotSupported, Translation
from woob.tools.backend import Module

from .browser import GoogleTranslateBrowser


__all__ = ["GoogleTranslateModule"]


class GoogleTranslateModule(Module, CapTranslate):
    MAINTAINER = "Lucien Loiseau"
    EMAIL = "loiseau.lucien@gmail.com"
    VERSION = "3.7"
    LICENSE = "AGPLv3+"
    NAME = "googletranslate"
    DESCRIPTION = "Google translation web service"
    BROWSER = GoogleTranslateBrowser

    def translate(self, lan_from, lan_to, text):

        googlelanguage = self.browser.get_supported_languages()

        languages_from = [k for k in googlelanguage.keys() if lan_from == k or f"{lan_from}-" in k]
        languages_to = [k for k in googlelanguage.keys() if lan_to == k or f"{lan_to}-" in k]

        if not (languages_from and languages_to):
            googlelanguage = {k.split("-")[0]: v for k, v in googlelanguage.items()}
            raise LanguageNotSupported(
                msg=f"This language is not supported. Please use one of the following one : {googlelanguage}"
            )

        for l_from in languages_from:
            for l_to in languages_to:
                translation = Translation(0)
                translation.lang_src = l_from
                translation.lang_dst = l_to
                translation.text = self.browser.translate(lan_from, lan_to, text)

                if not empty(translation.text):
                    yield translation
