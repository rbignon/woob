# flake8: compatible

# Copyright(C) 2023     Budget Insight
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

from woob.capabilities.captcha import CapCaptchaSolver
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword

from .browser import TwoCaptchaBrowser


__all__ = ['TwoCaptchaModule']


class TwoCaptchaModule(Module, CapCaptchaSolver):
    NAME = 'twocaptcha'
    DESCRIPTION = '2captcha, FunCaptcha solving service'
    MAINTAINER = 'Thomas Touhey'
    EMAIL = 'thomas.touhey@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.7'

    # Usually yields that the captcha is unsolvable around the 40th iteration.
    RETRIES = 50
    WAIT_TIME = 5

    CONFIG = BackendConfig(
        ValueBackendPassword(
            'api_key',
            label='API key',
            regexp='^[a-z0-9]{32}$',
        ),
    )

    BROWSER = TwoCaptchaBrowser

    def create_default_browser(self):
        return self.create_browser(self.config['api_key'].get())

    def create_job(self, job):
        return self.browser.create_job(job)

    def poll_job(self, job):
        return self.browser.poll_job(job)

    def report_wrong_solution(self, job):
        return self.browser.report_wrong_solution(job)

    def get_balance(self):
        return self.browser.get_balance()
