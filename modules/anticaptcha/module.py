# -*- coding: utf-8 -*-

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

# flake8: compatible

from __future__ import unicode_literals

from woob.tools.backend import Module, BackendConfig
from woob.capabilities.captcha import (
    CapCaptchaSolver, ImageCaptchaJob, RecaptchaJob, RecaptchaV3Job, RecaptchaV2Job, FuncaptchaJob,
    HcaptchaJob,
)
from woob.tools.value import ValueBackendPassword

from .browser import AnticaptchaBrowser


__all__ = ['AnticaptchaModule']


class AnticaptchaModule(Module, CapCaptchaSolver):
    NAME = 'anticaptcha'
    DESCRIPTION = 'Anti-Captcha website'
    MAINTAINER = 'Vincent A'
    EMAIL = 'dev@indigo.re'
    LICENSE = 'AGPLv3+'
    VERSION = '3.1'

    CONFIG = BackendConfig(
        ValueBackendPassword('api_key', label='API key', regexp='^[0-9a-f]+$'),
        # TODO support proxy option
    )

    BROWSER = AnticaptchaBrowser

    def create_default_browser(self):
        return self.create_browser(self.config['api_key'].get(), None)

    def create_job(self, job):
        if isinstance(job, ImageCaptchaJob):
            job.id = self.browser.post_image(job.image)
        elif isinstance(job, RecaptchaJob):
            job.id = self.browser.post_recaptcha(job.site_url, job.site_key)
        elif isinstance(job, RecaptchaV3Job):
            job.id = self.browser.post_gcaptchav3(job.site_url, job.site_key, job.action, job.min_score)
        elif isinstance(job, RecaptchaV2Job):
            job.id = self.browser.post_nocaptcha(job.site_url, job.site_key)
        elif isinstance(job, FuncaptchaJob):
            job.id = self.browser.post_funcaptcha(job.site_url, job.site_key, job.sub_domain)
        elif isinstance(job, HcaptchaJob):
            job.id = self.browser.post_hcaptcha(job.site_url, job.site_key)
        else:
            raise NotImplementedError()

    def poll_job(self, job):
        return self.browser.poll(job)

    def report_wrong_solution(self, job):
        if isinstance(job, ImageCaptchaJob):
            self.browser.report_wrong_image(job)
        if isinstance(job, (RecaptchaV2Job, RecaptchaJob, RecaptchaV3Job)):
            self.browser.report_wrong_recaptcha(job)

    def get_balance(self):
        return self.browser.get_balance()
