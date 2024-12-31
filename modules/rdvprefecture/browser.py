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

from woob.browser.browsers import PagesBrowser, StatesMixin
from woob.browser.url import URL
from woob.capabilities.captcha import InvalidCaptcha
from woob.tools.url import get_url_param

from .pages import CaptchaHTMLPage, CaptchaImagePage, PrepareApplicationPage, SelectSlotPage, ValidateCaptchaPage


class RDVPrefectureBrowser(PagesBrowser, StatesMixin):
    __states__ = ("captcha_vars",)

    BASEURL = 'https://www.rdv-prefecture.interieur.gouv.fr/'
    CAPTCHETAT_BASEURL = "https://api.piste.gouv.fr/piste/captcha/"

    captcha_html_endpoint = URL(
        r"simple-captcha-endpoint\?get=html&c=(?P<captcha_style>[^&]+)",
        CaptchaHTMLPage,
        base="CAPTCHETAT_BASEURL",
    )
    captcha_image_endpoint = URL(
        r"simple-captcha-endpoint\?get=image&c=(?P<captcha_style>[^&]+)&t=(?P<captcha_id>[^&]+)",
        CaptchaImagePage,
        base="CAPTCHETAT_BASEURL",
    )

    prepare_application = URL(
        r"rdvpref/reservation/demarche/(?P<proc_id>\d+)/cgu/",
        PrepareApplicationPage,
    )
    validate_captcha = URL(
        r"rdvpref/reservation/demarche/(?P<proc_id>\d+)/_validerCaptcha",
        ValidateCaptchaPage,
    )
    select_slot = URL(
        r"rdvpref/reservation/demarche/(?P<proc_id>\d+)/creneau/",
        SelectSlotPage,
    )

    captcha_vars: dict[str, str] | None
    """Identifying data of the last requested captcha."""

    def __init__(self, config, *args, **kwargs):
        self.config = config
        self.captcha_vars = None
        super().__init__(*args, **kwargs)

    def check_slots_available(self, procedure_id: int) -> bool:
        """Check if slots are available.

        :param procedure_id: Procedure identifier.
        :return: Whether slots are available.
        """
        captcha_response = self.config["captcha_response"].get()
        if not captcha_response or not self.captcha_vars:
            self.prepare_application.go(proc_id=procedure_id)
            self.page.raise_captcha_question()

        captcha_data = {**self.captcha_vars, "captchaUsercode": captcha_response}
        self.captcha_vars = None

        self.validate_captcha.go(proc_id=procedure_id, data=captcha_data)
        if (
            self.prepare_application.is_here()
            and get_url_param(self.page.url, "error", default="") == "invalidCaptcha"
        ):
            raise InvalidCaptcha()

        assert self.select_slot.is_here()

        return self.page.check_slots_available()
