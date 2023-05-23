# -*- coding: utf-8 -*-

# Copyright(C) 2021 Vincent A
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

from woob.capabilities.messages import CapMessages, Message, Thread
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import Value
from woob.tools.capabilities.messages.threading import build_linear_thread

from .browser import TinyViewBrowser


__all__ = ["TinyViewModule"]


class TinyViewModule(Module, CapMessages):
    NAME = "tinyview"
    DESCRIPTION = "TinyView"
    MAINTAINER = "Vincent A"
    EMAIL = "dev@indigo.re"
    LICENSE = "LGPLv3+"
    VERSION = "3.6"

    BROWSER = TinyViewBrowser

    CONFIG = BackendConfig(
        Value("comic", label="Comic"),
    )

    def create_default_browser(self):
        return self.create_browser(self.config["comic"].get())

    def _build_message(self, entry):
        msg = Message()
        msg.id = entry.id
        msg.date = entry.date
        msg.title = entry.title
        msg.url = entry.url
        msg.sender = self.config["comic"].get()

        msg.flags = Message.IS_HTML
        msg.content = "\n\n".join(
            f"""
                <figure>
                    <img src="{img.url}"/>
                    <figcaption>{img.description or img.title or ""}</figcaption>
                </figure>
            """
            for img in entry.images
        )

        msg._entry = entry
        return msg

    def _build_thread(self, entry):
        message = self._build_message(entry)
        thread = build_linear_thread([message])
        thread._entry = entry
        return thread

    def iter_threads(self):
        for entry in self.browser.iter_entries():
            # yield self._build_thread(entry)
            yield self.get_thread(entry.id)

    def get_thread(self, id):
        return self._build_thread(self.browser.get_entry(id))

    def fill_image(self, img, fields):
        if "data" in fields:
            img.data = self.browser.open(img.url).content

    def fill_thread(self, thread, fields):
        if "root" in fields:
            ...

    OBJECTS = {
        Thread: fill_thread,
    }
