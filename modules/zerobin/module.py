# -*- coding: utf-8 -*-

# Copyright(C) 2016      Vincent A
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


from woob.capabilities.paste import CapPaste
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import Value, ValueBool

from .browser import ZerobinBrowser, ZeroPaste


__all__ = ["ZerobinModule"]


class ZerobinModule(Module, CapPaste):
    NAME = "zerobin"
    DESCRIPTION = "ZeroBin/0bin/PrivateBin encrypted pastebin"
    MAINTAINER = "Vincent A"
    EMAIL = "dev@indigo.re"
    LICENSE = "AGPLv3+"
    VERSION = "3.7"
    CONFIG = BackendConfig(
        Value("url", label="URL of the zerobin/0bin/privatebin", regexp="https?://.*", default="https://zerobin.net"),
        ValueBool("discussion", label="Allow paste comments (ZeroBin only)", default=False),
    )

    BROWSER = ZerobinBrowser

    def create_default_browser(self):
        return self.create_browser(self.config["url"].get(), self.config["discussion"].get())

    def can_post(self, contents, title=None, public=None, max_age=None):
        """
        Checks if the paste can be pasted by this backend.
        Some properties are considered required (public/private, max_age) while others
        are just bonuses (language).

        contents: Can be used to check encodability, maximum length, etc.
        title: Can be used to check length, allowed characters. Should not be required.
        public: True must be public, False must be private, None do not care.
        max_age: Maximum time to live in seconds.

        A score of 0 means the backend is not suitable.
        A score of 1 means the backend is suitable.
        Higher scores means it is more suitable than others with a lower score.

        :rtype: int
        :returns: score
        """
        if public:
            return 0
        return self.browser.can_post(contents, max_age)

    def get_paste(self, id):
        if "#" not in id:
            return
        elif id.startswith("http://") or id.startswith("https://"):
            if not id.startswith(self.config["url"].get()):
                return
        return self.browser.get_paste(id)

    def new_paste(self, *args, **kwargs):
        return ZeroPaste(*args, **kwargs)

    def post_paste(self, paste, max_age=None):
        self.browser.post_paste(paste, max_age)
