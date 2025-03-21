# Copyright(C) 2011-2021 Romain Bignon
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

from woob.capabilities.base import NotLoaded
from woob.tools.backend import Module
from woob.tools.capabilities.paste import BasePasteModule

from .browser import PastealaconBrowser, PastealaconPaste


class PastealaconModule(Module, BasePasteModule):
    NAME = "pastealacon"
    MAINTAINER = "Laurent Bachelier"
    EMAIL = "laurent@bachelier.name"
    VERSION = "3.7"
    DESCRIPTION = "Paste à la con text sharing tool"
    LICENSE = "AGPLv3+"
    BROWSER = PastealaconBrowser

    EXPIRATIONS = {
        24 * 3600: "d",
        24 * 3600 * 30: "m",
        False: "f",
    }

    def new_paste(self, *args, **kwargs):
        return PastealaconPaste(*args, **kwargs)

    def can_post(self, contents, title=None, public=None, max_age=None):
        try:
            contents.encode("ISO-8859-1")
        except UnicodeEncodeError:
            return 0
        if public is False:
            return 0
        if max_age is not None:
            if self.get_closest_expiration(max_age) is None:
                return 0
        # the "title" is filtered (does not even accepts dots)
        if not title or re.match(r"^\w+$", title) and len(title) <= 24:
            return 2
        return 1

    def get_paste(self, _id):
        return self.browser.get_paste(_id)

    def fill_paste(self, paste, fields):
        # if we only want the contents
        if fields == ["contents"]:
            if paste.contents is NotLoaded:
                contents = self.browser.get_contents(paste.id)
                paste.contents = contents
        # get all fields
        elif fields is None or len(fields):
            self.browser.fill_paste(paste)
        return paste

    def post_paste(self, paste, max_age=None):
        if max_age is not None:
            expiration = self.get_closest_expiration(max_age)
        else:
            expiration = None
        self.browser.post_paste(paste, expiration=self.EXPIRATIONS.get(expiration))

    OBJECTS = {PastealaconPaste: fill_paste}
