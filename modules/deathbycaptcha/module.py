# Copyright(C) 2018      Vincent A
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

from woob.capabilities.captcha import CapCaptchaSolver, ImageCaptchaJob, RecaptchaV2Job
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import Value, ValueBackendPassword

from .browser import DeathbycaptchaBrowser


__all__ = ["DeathbycaptchaModule"]


class DeathbycaptchaModule(Module, CapCaptchaSolver):
    NAME = "deathbycaptcha"
    DESCRIPTION = "Death By Captcha"
    MAINTAINER = "Vincent A"
    EMAIL = "dev@indigo.re"
    LICENSE = "AGPLv3+"
    VERSION = "3.7"

    CONFIG = BackendConfig(
        Value("login"),
        ValueBackendPassword("password"),
    )

    BROWSER = DeathbycaptchaBrowser

    def create_default_browser(self):
        return self.create_browser(self.config["login"].get(), self.config["password"].get())

    def create_job(self, job):
        if isinstance(job, ImageCaptchaJob):
            job.id = self.browser.create_job(job.image)
        elif isinstance(job, RecaptchaV2Job):
            job.id = self.browser.create_recaptcha2_job(job.site_url, job.site_key)
        else:
            raise NotImplementedError()

    def poll_job(self, job):
        job.solution = self.browser.poll(job.id)
        return job.solution is not None
