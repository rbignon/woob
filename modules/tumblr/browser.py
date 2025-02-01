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

import re
from datetime import datetime

from woob.browser.browsers import APIBrowser
from woob.browser.filters.standard import CleanText
from woob.capabilities.gallery import BaseImage
from woob.capabilities.image import Thumbnail
from woob.tools.json import json


class TumblrBrowser(APIBrowser):
    def __init__(self, baseurl, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.BASEURL = baseurl

    def consent(self):
        response = self.open(self.BASEURL)
        html = response.text
        token = re.search(r'name="tumblr-form-key".*?content="([^"]*)"', html).group(1)

        data = {
            "eu_resident": False,  # i don't want to live on this planet anymore
            "gdpr_is_acceptable_age": True,
            "gdpr_consent_core": True,
            "gdpr_consent_first_party_ads": True,
            "gdpr_consent_third_party_ads": True,
            "gdpr_consent_search_history": True,
            "redirect_to": self.BASEURL,
        }
        headers = {
            "X-tumblr-form-key": token,
            "Referer": response.url,
        }
        super().request("https://www.tumblr.com/svc/privacy/consent", data=data, headers=headers)

    def request(self, *args, **kwargs):
        def perform():
            # JSONP
            r = super(TumblrBrowser, self).open(*args, **kwargs).text
            r = re.sub(r"^var tumblr_api_read = (.*);$", r"\1", r)
            return json.loads(r)

        try:
            return perform()
        except ValueError:
            self.consent()
            return perform()

    def get_title_icon(self):
        r = self.request("/api/read/json?type=photo&num=1&start=0&filter=text")
        icon = None
        if r["posts"]:
            icon = r["posts"][0]["tumblelog"]["avatar_url_512"]
        return (r["tumblelog"]["title"], icon)

    def iter_images(self, gallery):
        index = 0
        offset = 0
        step = 50

        while True:
            r = self.request("/api/read/json?type=photo&filter=text", params={"start": offset, "num": step})
            for post in r["posts"]:
                for img in self._images_from_post(post, index, gallery):
                    yield img
                    index += 1

            offset += step
            if not r["posts"] or offset >= r["posts-total"]:
                break

    def _images_from_post(self, post, index, gallery):
        if post["type"] == "regular":
            try:
                r = self.request("/api/read/json?type=photo", params={"id": post["id"]})
            except ValueError:
                self.logger.warning("uh oh, no json for %r", post["id"])
                return
            match = re.search(r'(https://\d+\.media\.tumblr.com([^\\"]+))', r["posts"][0]["regular-body"])
            if not match:
                return
            img = BaseImage(
                id=post["id"],
                index=index,
                gallery=gallery,
                url=match.group(1),
                thumbnail=Thumbnail(match.group(1)),
            )
            yield img

            return

        # main photo only if single
        if not post["photos"]:
            img = BaseImage(
                index=index,
                gallery=gallery,
                url=post["photo-url-1280"],
                thumbnail=Thumbnail(post["photo-url-250"]),
            )
            img.id = post["id"]
            img.title = CleanText().filter(post["photo-caption"])
            img.date = datetime.strptime(post["date-gmt"], "%Y-%m-%d %H:%M:%S %Z")
            img._page_url = post["url"]
            yield img

        # if multiple
        for photo in post["photos"]:
            img = BaseImage(
                index=index,
                gallery=gallery,
                url=photo["photo-url-1280"],
                thumbnail=Thumbnail(photo["photo-url-250"]),
            )
            img.id = "{}.{}".format(post["id"], photo["offset"])
            index += 1
            img.title = CleanText().filter(photo["caption"] or post["photo-caption"])
            img.date = datetime.strptime(post["date-gmt"], "%Y-%m-%d %H:%M:%S %Z")
            img._page_url = post["url"]
            yield img

    def open_img(self, url):
        return self.open(url, headers={"Accept": "*/*"})
