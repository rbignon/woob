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

from woob.browser.browsers import PagesBrowser
from woob.browser.url import URL
from woob.capabilities.captcha import (
    CaptchaError, FuncaptchaJob, HcaptchaJob, InsufficientFunds,
    InvalidCaptcha, RecaptchaV2Job, RecaptchaV3Job, UnsolvableCaptcha,
)
from woob.exceptions import BrowserIncorrectPassword, BrowserUserBanned

from .pages import BalancePage, CaptchaPage


class TwoCaptchaBrowser(PagesBrowser):
    """Browser for the 2captcha resolver service.

    More documentation on the API can be found here:
    https://2captcha.com/2captcha-api
    """

    BASEURL = 'https://2captcha.com/'

    in_ = URL(r'in.php', CaptchaPage)
    res = URL(r'res.php')

    EXCEPTIONS = {
        'ERROR_WRONG_USER_KEY': BrowserIncorrectPassword('Invalid key format'),
        'ERROR_KEY_DOES_NOT_EXIST': BrowserIncorrectPassword('Invalid key'),
        'ERROR_ZERO_BALANCE': InsufficientFunds(),
        'ERROR_NO_SLOT_AVAILABLE': CaptchaError('No slot available'),
        'ERROR_ZERO_CAPTCHA_FILESIZE': InvalidCaptcha('Image size <100B'),
        'ERROR_TOO_BIG_CAPTCHA_FILESIZE': InvalidCaptcha('Image size >100KiB'),
        'ERROR_WRONG_FILE_EXTENSION': InvalidCaptcha('Unsupported file extension'),
        'ERROR_IMAGE_TYPE_NOT_SUPPORTED': InvalidCaptcha('Unsupported file type'),
        'ERROR_UPLOAD': InvalidCaptcha('Malformed image'),
        'ERROR_IP_NOT_ALLOWED': BrowserUserBanned(),
        'IP_BANNED': BrowserUserBanned(),
        'ERROR_CAPTCHA_UNSOLVABLE': UnsolvableCaptcha(),
    }

    def __init__(self, api_key, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = api_key

    def get_captcha_response(self, page):
        status = page.get_status()
        if status == 0:
            code = page.get_response()
            if code in ('CAPCHA_NOT_READY', 'CAPTCHA_NOT_READY'):  # sic
                return None

            try:
                raise self.EXCEPTIONS[code]
            except KeyError:
                raise AssertionError(f'Unhandled error: {code}')
        elif status == 1:
            return page.get_response()

        raise AssertionError(f'Unhandled status: {status}')

    def create_job(self, job):
        params = {'key': self.api_key, 'json': '1'}
        if isinstance(job, FuncaptchaJob):
            params['method'] = 'funcaptcha'
            params['publickey'] = job.site_key
            if job.sub_domain:
                params['surl'] = f'https://{job.sub_domain}'
            if job.site_url:
                params['pageurl'] = job.site_url
            if job.data:
                for key, value in job.data.items():
                    params[f'data[{key}]'] = value
        elif isinstance(job, RecaptchaV2Job):
            params['method'] = 'userrecaptcha'
            params['googlekey'] = job.site_key
            params['pageurl'] = job.site_url
        elif isinstance(job, RecaptchaV3Job):
            params['method'] = 'userrecaptcha'
            params['version'] = 'v3'
            params['googlekey'] = job.site_key
            params['pageurl'] = job.site_url
            if job.is_enterprise:
                params['enterprise'] = '1'
            if job.action:
                params['action'] = job.action
            if job.min_score:
                params['min_score'] = job.min_score
        elif isinstance(job, HcaptchaJob):
            params['method'] = 'hcaptcha'
            params['sitekey'] = job.site_key
            params['pageurl'] = job.site_url
        else:
            raise NotImplementedError()

        page = self.in_.open(data=params)
        job.id = self.get_captcha_response(page)
        return job.id

    def poll_job(self, job):
        response = self.open(
            self.res.build(),
            data={
                'action': 'get',
                'id': job.id,
                'key': self.api_key,
                'json': '1',
            },
            page=CaptchaPage,
        )

        solution = self.get_captcha_response(response.page)
        if solution is None:
            return False

        job.solution = solution
        return True

    def report_wrong_solution(self, job):
        self.res.open(
            data={
                'action': 'reportbad',
                'id': job.id,
                'key': self.api_key,
            },
        )

    def get_balance(self):
        self.location(
            self.res.build(),
            data={'action': 'getbalance', 'key': self.api_key, 'json': '1'},
            page=BalancePage,
        )

        return self.page.get_balance()
