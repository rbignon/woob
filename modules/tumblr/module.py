# Copyright(C) 2017      Vincent A
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

from urllib.parse import urlparse

from woob.browser.exceptions import ClientError, HTTPNotFound
from woob.capabilities.gallery import BaseGallery, BaseImage, CapGallery, Thumbnail
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import Value

from .browser import TumblrBrowser


__all__ = ["TumblrModule"]


class TumblrModule(Module, CapGallery):
    NAME = "tumblr"
    DESCRIPTION = "images in tumblr blogs"
    MAINTAINER = "Vincent A"
    EMAIL = "dev@indigo.re"
    LICENSE = "AGPLv3+"
    VERSION = "3.7"
    CONFIG = BackendConfig(Value("url", label="URL of the tumblr", regexp="https?://.+"))

    BROWSER = TumblrBrowser

    def create_default_browser(self):
        return self.create_browser(self.url())

    def url(self):
        return self.config["url"].get()

    def get_gallery(self, _id):
        title, icon = self.browser.get_title_icon()
        if icon:
            icon = Thumbnail(icon)
        return BaseGallery(_id, title=title, url=self.url(), thumbnail=icon)

    def search_galleries(self, pattern, sortby=CapGallery.SEARCH_RELEVANCE):
        pattern = pattern.lower()
        url = self.url()
        if pattern in url or pattern in self.browser.get_title_icon()[0].lower():
            yield self.get_gallery(urlparse(url).netloc)

    def iter_gallery_images(self, gallery):
        yield from self.browser.iter_images(gallery)

    def fill_img(self, img, fields):
        if "data" in fields:
            try:
                img.data = self.browser.open_img(img.url).content
            except (ClientError, HTTPNotFound):
                img.data = b""
        if "thumbnail" in fields and img.thumbnail:
            self.fill_img(img.thumbnail, ("data",))

    OBJECTS = {
        BaseImage: fill_img,
        BaseGallery: fill_img,
    }
