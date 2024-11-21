# Copyright(C) 2024 Thomas Touhey <thomas+woob@touhey.fr>
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

from __future__ import annotations

from woob.browser.filters.html import Attr, HasElement
from woob.browser.pages import HTMLPage, PartialHTMLPage, RawPage
from woob.capabilities.captcha import ImageCaptchaQuestion
from woob.tools.url import get_url_param


class CaptchaHTMLPage(PartialHTMLPage):
    def get_captcha_id(self) -> str:
        url = Attr("//script", "src")(self.doc)
        return get_url_param(url, "t")

    def get_additional_vars(self) -> dict[str, str]:
        return {
            elt.attrib["name"]: elt.attrib["value"]
            for elt in self.doc.xpath("//input[@type='hidden']")
            if "name" in elt.attrib and "value" in elt.attrib
        }


class CaptchaImagePage(RawPage):
    pass


class PrepareApplicationPage(HTMLPage):
    def raise_captcha_question(self) -> None:
        # We need to find a custom element <rdv-captchetat> with the required
        # data for solving the token.
        captcha_token = Attr("//rdv-captchetat", "token")(self.doc)
        captcha_style = Attr("//rdv-captchetat", "captcha-style-name")(self.doc)

        html_page = self.browser.captcha_html_endpoint.open(
            captcha_style=captcha_style,
            headers={"Authorization": f"Bearer {captcha_token}"},
        )

        captcha_id = html_page.get_captcha_id()
        additional_vars = html_page.get_additional_vars()

        image_page = self.browser.captcha_image_endpoint.open(
            captcha_style=captcha_style,
            captcha_id=captcha_id,
            headers={"Authorization": f"Bearer {captcha_token}"},
        )

        self.browser.captcha_vars = {
            "captchaId": captcha_id,
            **additional_vars,
        }
        raise ImageCaptchaQuestion(image_data=image_page.doc)


class ValidateCaptchaPage(RawPage):
    pass


class SelectSlotPage(HTMLPage):
    def check_slots_available(self) -> bool:
        return not HasElement(
            "//*[contains(text(), 'Aucun créneau disponible')]",
        )(self.doc)
