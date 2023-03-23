# Copyright(C) 2018 Vincent A
#
# This file is part of woob.
#
# woob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# woob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with woob. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from time import sleep
from typing import Any

from woob.exceptions import CaptchaQuestion

from .base import (
    BaseObject, BoolField, BytesField, Capability, Field, FloatField,
    StringField, UserError,
)


__all__ = [
    'CapCaptchaSolver',
    'SolverJob', 'RecaptchaJob', 'RecaptchaV2Job', 'RecaptchaV3Job',
    'ImageCaptchaJob', 'HcaptchaJob', 'GeetestV4Job', 'TurnstileQuestion',
    'CaptchaError', 'UnsolvableCaptcha', 'InvalidCaptcha', 'InsufficientFunds',
    'ImageCaptchaQuestion', 'RecaptchaV2Question', 'RecaptchaQuestion',
    'GeetestV4Question', 'RecaptchaV3Question', 'FuncaptchaQuestion',
    'HcaptchaQuestion', 'TurnstileQuestion',
    'exception_to_job',
]


class SolverJob(BaseObject):
    solution = StringField('CAPTCHA solution')


class RecaptchaJob(SolverJob):
    site_url = StringField('Site URL for ReCaptcha service')
    site_key = StringField('Site key for ReCaptcha service')

    solution_challenge = StringField('Challenge ID of the solution (output value)')


class RecaptchaV3Job(SolverJob):
    site_url = StringField('Site URL for ReCaptcha service')
    site_key = StringField('Site key for ReCaptcha service')
    action = StringField('Website owner defines what user is doing on the page through this parameter.')
    min_score = FloatField('Minimum score the reCaptcha response is required to have to be valid.')
    is_enterprise = BoolField('If it is a reCaptcha enterprise')


class RecaptchaV2Job(SolverJob):
    site_url = StringField('Site URL for NoCaptcha service')
    site_key = StringField('Site key for NoCaptcha service')


class FuncaptchaJob(SolverJob):
    site_url = StringField('Site URL for FunCaptcha service')
    site_key = StringField('Site key for FunCaptcha service')
    sub_domain = StringField('Required for some complex cases, but Funcaptcha integrations run without it')
    data = Field('Required for some complex cases', dict)


class HcaptchaJob(SolverJob):
    site_url = StringField('Site URL for HCaptcha service')
    site_key = StringField('Site key for HCaptcha service')


class GeetestV4Job(SolverJob):
    site_url = StringField('Site URL for Geetest service')
    gt = StringField('Site domain public key')


class TurnstileJob(SolverJob):
    site_url = StringField('Site URL for Turnstile service')
    site_key = StringField('Site key for Turnstile service')


class ImageCaptchaJob(SolverJob):
    image = BytesField('data of the image to solve')


class CaptchaError(UserError):
    """Generic solving error"""


class InvalidCaptcha(CaptchaError):
    """CAPTCHA cannot be used (e.g. invalid image format)"""


class UnsolvableCaptcha(CaptchaError):
    """CAPTCHA is too hard or impossible"""


class InsufficientFunds(CaptchaError):
    """Not enough funds to pay solution"""


class ImageCaptchaQuestion(CaptchaQuestion):
    """The site signals to us that an image captcha should be solved."""

    type = 'image_captcha'

    image_data = None

    def __init__(
        self,
        image_data: bytes
    ):
        super().__init__(self.type, image_data=image_data)


class RecaptchaV2Question(CaptchaQuestion):
    """The site signals to us that a recaptchav2 challenge should be solved."""

    type = 'g_recaptcha'

    website_key = None
    website_url = None

    def __init__(
        self,
        website_key: str,
        website_url: str
    ):
        super().__init__(self.type, website_key=website_key, website_url=website_url)


class RecaptchaQuestion(CaptchaQuestion):
    """The site signals to us that a recaptcha challenge should be solved."""

    type = 'g_recaptcha'

    website_key = None
    website_url = None

    def __init__(
        self,
        website_key: str,
        website_url: str
    ):
        super().__init__(self.type, website_key=website_key, website_url=website_url)


class GeetestV4Question(CaptchaQuestion):
    """The site signals to us that a geetestv4 challenge should be solved."""

    type = 'GeeTestTaskProxyless'

    website_url = None
    gt = None

    def __init__(
        self,
        website_url: str,
        gt: Any
    ):
        super().__init__(self.type, website_url=website_url, gt=gt)


class RecaptchaV3Question(CaptchaQuestion):
    """The site signals to us that a recaptchav3 challenge should be solved."""

    type = 'g_recaptcha'

    website_key = None
    website_url = None
    action = None
    min_score = None
    is_enterprise = False

    def __init__(
        self,
        website_key: str,
        website_url: str,
        action: str | None = None,
        min_score: float | None = None,
        is_enterprise: bool = False
    ):
        super().__init__(self.type, website_key=website_key, website_url=website_url)
        self.action = action
        self.min_score = min_score
        self.is_enterprise = is_enterprise


class FuncaptchaQuestion(CaptchaQuestion):
    """The site signals to us that a Funcaptcha challenge should be solved."""

    type = 'funcaptcha'

    website_key = None
    website_url = None
    sub_domain = None

    data = None
    """Optional additional data, as a dictionary.

    For example, a site could transmit a 'blob' property which you should
    get, and transmit as {'blob': your_blob_value} through this property.
    """

    def __init__(
        self,
        website_key: str,
        website_url: str,
        sub_domain: str | None = None,
        data: bytes | None = None
    ):
        super().__init__(
            self.type,
            website_key=website_key,
            website_url=website_url,
            sub_domain=sub_domain,
            data=data,
        )


class HcaptchaQuestion(CaptchaQuestion):
    """The site signals to us that an HCaptcha challenge should be solved."""

    type = 'hcaptcha'

    website_key = None
    website_url = None

    def __init__(
        self,
        website_key: str,
        website_url: str
    ):
        super().__init__(self.type, website_key=website_key, website_url=website_url)


class TurnstileQuestion(CaptchaQuestion):
    """A Cloudflare Turnstile captcha has been encountered and requires resolution."""

    type = 'TurnstileTaskProxyless'

    website_key = None
    website_url = None

    def __init__(
        self,
        website_key: str,
        website_url: str
    ):
        super().__init__(self.type, website_key=website_key, website_url=website_url)


def exception_to_job(exc):
    if isinstance(exc, RecaptchaQuestion):
        job = RecaptchaJob()
        job.site_url = exc.website_url
        job.site_key = exc.website_key
    elif isinstance(exc, RecaptchaV3Question):
        job = RecaptchaV3Job()
        job.site_url = exc.website_url
        job.site_key = exc.website_key
        job.action = exc.action
        job.min_score = exc.min_score
        job.is_enterprise = exc.is_enterprise
    elif isinstance(exc, RecaptchaV2Question):
        job = RecaptchaV2Job()
        job.site_url = exc.website_url
        job.site_key = exc.website_key
    elif isinstance(exc, FuncaptchaQuestion):
        job = FuncaptchaJob()
        job.site_url = exc.website_url
        job.site_key = exc.website_key
        job.sub_domain = exc.sub_domain
        job.data = exc.data
    elif isinstance(exc, ImageCaptchaQuestion):
        job = ImageCaptchaJob()
        job.image = exc.image_data
    elif isinstance(exc, HcaptchaQuestion):
        job = HcaptchaJob()
        job.site_url = exc.website_url
        job.site_key = exc.website_key
    elif isinstance(exc, GeetestV4Question):
        job = GeetestV4Job()
        job.site_url = exc.website_url
        job.gt = exc.gt
    elif isinstance(exc, TurnstileQuestion):
        job = TurnstileJob()
        job.site_url = exc.website_url
        job.site_key = exc.website_key
    else:
        raise NotImplementedError()

    return job


class CapCaptchaSolver(Capability):
    """
    Provide CAPTCHA solving
    """

    RETRIES = 30
    WAIT_TIME = 2

    def create_job(self, job: SolverJob):
        """Start a CAPTCHA solving job

        The `job.id` shall be filled. The CAPTCHA is not solved yet when the method returns.

        :param job: job to start
        :type job: :class:`SolverJob`
        :raises: :class:`NotImplementedError` if CAPTCHA type is not supported
        :raises: :class:`CaptchaError` in case of other error
        """
        raise NotImplementedError()

    def poll_job(self, job: SolverJob) -> bool:
        """Check if a job was solved

        If `job` is solved, return True and fill `job.solution`.
        Return False if solution is still pending.
        In case of solving problem, an exception may be raised.

        It should not wait for the solution but return the current state.

        :param job: job to check and to fill when solved
        :type job: :class:`SolverJob`
        :returns: True if the job was solved
        :rtype: bool
        :raises: :class:`CaptchaError`
        """
        raise NotImplementedError()

    def solve_captcha_blocking(self, job: SolverJob):
        """Start a CAPTCHA solving job and wait for its solution

        :param job: job to start and solve
        :type job: :class:`SolverJob`
        :raises: :class:`CaptchaError`
        """

        return self.solve_catpcha_blocking(job)

    def solve_catpcha_blocking(self, job: SolverJob) -> SolverJob | None:
        """Typoed method that will disappear in an upcoming version"""

        self.create_job(job)
        for i in range(self.RETRIES):
            sleep(self.WAIT_TIME)
            if self.poll_job(job):
                return job

        return None

    def report_wrong_solution(self, job: SolverJob):
        """Report a solved job as a wrong solution

        Sometimes, jobs are solved, but the solution is rejected by the CAPTCHA
        site because the solution is wrong.
        This method reports the solution as wrong to the CAPTCHA solver.

        :param job: job to flag
        :type job: :class:`SolverJob`
        """
        raise NotImplementedError()

    def get_balance(self) -> float:
        """Get the prepaid balance left

        :rtype: float
        """
        raise NotImplementedError()
