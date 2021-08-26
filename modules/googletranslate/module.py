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
"backend for http://translate.google.com"

from __future__ import unicode_literals

from woob.capabilities.translate import CapTranslate, Translation, TranslationFail, LanguageNotSupported
from woob.capabilities.base import empty
from woob.tools.backend import Module

from .browser import GoogleTranslateBrowser

__all__ = ['GoogleTranslateModule']


class GoogleTranslateModule(Module, CapTranslate):
    MAINTAINER = u'Lucien Loiseau'
    EMAIL = 'loiseau.lucien@gmail.com'
    VERSION = '3.1'
    LICENSE = 'AGPLv3+'
    NAME = 'googletranslate'
    DESCRIPTION = u'Google translation web service'
    BROWSER = GoogleTranslateBrowser

    def translate(self, lan_from, lan_to, text):
        googlelanguage = self.browser.get_supported_languages()
        if lan_from not in googlelanguage.keys():
            raise LanguageNotSupported(
                msg=f"This language is not supported. Please use one of the following one : {googlelanguage}")

        if lan_to not in googlelanguage.keys():
            raise LanguageNotSupported(
                msg=f"This language is not supported. Please use one of the following one : {googlelanguage}")

        translation = Translation(0)
        translation.lang_src = lan_from
        translation.lang_dst = lan_to
        translation.text = self.browser.translate(lan_from, lan_to, text)

        if empty(translation.text):
            raise TranslationFail()

        return translation
