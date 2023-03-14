# Copyright(C) 2014 Romain Bignon
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

import warnings
import importlib
from functools import wraps
from typing import List

from woob.tools.value import Value


__all__ = [
    'BrowserIncorrectPassword',
    'BrowserForbidden',
    'BrowserUserBanned',
    'BrowserUnavailable',
    'ScrapingBlocked',
    'BrowserInteraction',
    'BrowserQuestion',
    'OTPQuestion',
    'OTPSentType',
    'SentOTPQuestion',
    'OfflineOTPQuestion',
    'DecoupledMedium',
    'DecoupledValidation',
    'AppValidation',
    'AppValidationError',
    'AppValidationCancelled',
    'AppValidationExpired',
    'BrowserRedirect',
    'CaptchaQuestion',
    'WrongCaptchaResponse',
    'BrowserHTTPNotFound',
    'BrowserHTTPError',
    'BrowserHTTPSDowngrade',
    'BrowserSSLError',
    'ParseError',
    'FormFieldConversionWarning',
    'NoAccountsException',
    'ModuleInstallError',
    'ModuleLoadError',
    'ActionType',
    'ActionNeeded',
    'AuthMethodNotImplemented',
    'BrowserPasswordExpired',
    'NeedInteractive',
    'NeedInteractiveForRedirect',
    'NeedInteractiveFor2FA',
    'NotImplementedWebsite',
]


class BrowserIncorrectPassword(Exception):
    def __init__(self, message="", bad_fields=None):
        """
        :type message: str
        :param message: compatibility message for the user (mostly when bad_fields is not given)
        :type bad_fields: list[str]
        :param bad_fields: list of config field names which are incorrect, if it is known
        """

        super().__init__(*filter(None, [message]))
        self.bad_fields = bad_fields


class BrowserForbidden(Exception):
    pass


class BrowserUserBanned(BrowserIncorrectPassword):
    pass


class BrowserUnavailable(Exception):
    pass


class ScrapingBlocked(BrowserUnavailable):
    pass


class BrowserInteraction(Exception):
    pass


class BrowserQuestion(BrowserInteraction):
    """
    When raised by a browser,
    """
    def __init__(self, *fields):
        self.fields = fields

    def __str__(self):
        return ", ".join("{}: {}".format(
            field.id or field.label, field.description) for field in self.fields
        )


class OTPQuestion(BrowserQuestion):
    pass


class OTPSentType:
    UNKNOWN = "unknown"
    SMS = "sms"
    MOBILE_APP = "mobile_app"
    EMAIL = "email"
    DEVICE = "device"


class SentOTPQuestion(OTPQuestion):
    """Question when the OTP was sent by the site to the user (e.g. SMS)
    """

    def __init__(
        self, field_name, medium_type=OTPSentType.UNKNOWN, medium_label=None, message="",
        expires_at=None,
    ):
        """
        :type field_name: str
        :param field_name: name of the config field in which the OTP shall
                           be given to the module
        :type medium_type: OTPSentType
        :param medium_type: if known, where the OTP was sent
        :type medium_label: str
        :param medium_label: if known, label of where the OTP was sent,
                             e.g. the phone number in case of an SMS
        :type message: str
        :param message: compatibility message (used as the Value label)
        :type expires_at: datetime.datetime
        :param expires_at: date when the OTP expires and when replying is too late
        """

        self.message = message
        self.medium_type = medium_type
        self.medium_label = medium_label
        self.expires_at = expires_at

        super().__init__(Value(field_name, label=message))


class OfflineOTPQuestion(OTPQuestion):
    """Question when the user has to compute the OTP themself (e.g. card reader)
    """

    def __init__(self, field_name, input=None, medium_label=None, message="", expires_at=None):
        """
        :type field_name: str
        :param field_name: name of the config field in which the OTP shall
                           be given to the module
        :type input: str
        :param input: if relevant, input data for computing the OTP
        :type message: str
        :param message: compatibility message (used as the Value label)
        :type medium_label: str
        :param medium_label: if known, label of the device to use for generating
                             or reading the OTP, e.g. the card index for paper OTP
        :type expires_at: datetime.datetime
        :param expires_at: date when the OTP expires and when replying is too late
        """

        super().__init__(Value(field_name, label=message))
        self.input = input
        self.medium_label = medium_label
        self.expires_at = expires_at


class DecoupledMedium:
    UNKNOWN = "unknown"
    SMS = "sms"
    MOBILE_APP = "mobile_app"
    EMAIL = "email"


class DecoupledValidation(BrowserInteraction):
    def __init__(
        self, message='', resource=None, medium_type=DecoupledMedium.UNKNOWN, medium_label=None, expires_at=None,
        *values
    ):
        """
        :type medium_type: DecoupledMedium
        :param medium_type: if known, where the decoupled validation was sent
        :type medium_label: str
        :param medium_label: if known, label of where the decoupled validation was sent,
                             e.g. the phone number in case of an app
        :type expires_at: datetime.datetime
        :param expires_at: date when the OTP expires and when replying is too late
        """

        super().__init__(*values)
        self.medium_type = medium_type
        self.medium_label = medium_label
        self.message = message
        self.resource = resource
        self.expires_at = expires_at

    def __str__(self):
        return self.message


class AppValidation(DecoupledValidation):
    def __init__(self, *args, **kwargs):
        kwargs["medium_type"] = DecoupledMedium.MOBILE_APP
        super().__init__(*args, **kwargs)


class AppValidationError(Exception):
    def __init__(self, message=''):
        super().__init__(message)


class AppValidationCancelled(AppValidationError):
    pass


class AppValidationExpired(AppValidationError):
    pass


class BrowserRedirect(BrowserInteraction):
    def __init__(self, url, resource=None):
        self.url = url

        # Needed for transfer redirection
        self.resource = resource

    def __str__(self):
        return 'Redirecting to %s' % self.url


class CaptchaQuestion(Exception):
    """Site requires solving a CAPTCHA (base class)"""
    # could be improved to pass the name of the backendconfig key

    def __init__(self, type=None, **kwargs):
        super().__init__("The site requires solving a captcha")
        self.type = type
        for key, value in kwargs.items():
            setattr(self, key, value)


class WrongCaptchaResponse(Exception):
    """when website tell us captcha response is not good"""
    def __init__(self, message=None):
        super().__init__(message or "Captcha response is wrong")


class BrowserHTTPNotFound(Exception):
    pass


class BrowserHTTPError(Exception):
    pass


class BrowserHTTPSDowngrade(Exception):
    pass


class BrowserSSLError(BrowserUnavailable):
    pass


class ParseError(Exception):
    pass


class FormFieldConversionWarning(UserWarning):
    """
    A value has been set to a form's field and has been implicitly converted.
    """


class NoAccountsException(Exception):
    pass


class ModuleInstallError(Exception):
    pass


class ModuleLoadError(Exception):
    def __init__(self, module_name, msg):
        super().__init__(msg)
        self.module = module_name


class ActionType:
    # TODO use enum class
    ACKNOWLEDGE = 1
    """Must acknowledge new Terms of Service or some important message"""

    FILL_KYC = 2
    """User information must be filled on website"""

    ENABLE_MFA = 3
    """MFA must be enabled on website"""

    PERFORM_MFA = 4
    """Must perform MFA on website directly to unlock scraping

    It is different from `DecoupledValidation`.
    """

    PAYMENT = 5
    """Must pay site for the feature or pay again for the subscription which has ended"""

    CONTACT = 6
    """Must contact site support or a customer relation person for another problem

    The problem should ideally be described in `ActionNeeded.message`.
    """


class ActionNeeded(Exception):
    def __init__(
        self, message=None, *, locale=None, action_type=None, url=None, page=None,
    ):
        """
        An action must be performed directly, often on website.

        :param message: message from the site
        :type message: str
        :param locale: ISO4646 language tag of `message` (e.g. "en-US")
        :type locale: str
        :param action_type: type of action to perform
        :param url: URL of the page to go to resolve the action needed
        :type url: str
        :param page: user hint for when no URL can be given and the place where to perform the action is not obvious
        :type page: str
        """

        args = ()
        if message:
            args = (message,)

        super().__init__(*args)
        self.locale = locale
        self.action_type = action_type
        self.page = page
        self.url = url


class AuthMethodNotImplemented(ActionNeeded):
    pass


class BrowserPasswordExpired(ActionNeeded):
    pass


class NeedInteractive(Exception):
    pass


class NeedInteractiveForRedirect(NeedInteractive):
    """
    An authentication is required to connect and credentials are not supplied
    """
    pass


class NeedInteractiveFor2FA(NeedInteractive):
    """
    A 2FA is required to connect, credentials are supplied but not the second factor
    """
    pass


def implemented_websites(*cfg):
    """
    Decorator to raise NotImplementedWebsite for concerned website
    Will raise the exception for website not in arguments: ex ('ent', 'pro')
    """
    warnings.warn(
        'Do not use this decorator.',
        DeprecationWarning,
        stacklevel=2
    )

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not self.config['website'].get() in cfg:
                raise NotImplementedWebsite('This website is not yet implemented')

            return func(self, *args, **kwargs)
        return wrapper
    return decorator


class NotImplementedWebsite(NotImplementedError):
    """
    Exception for modules when a website is not yet available.
    """
    def __init__(self, *args, **kwargs):
        warnings.warn(
            'Do not use this exception.',
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(self, *args, **kwargs)


__deprecated__ = {
    'ImageCaptchaQuestion': 'woob.capabilities.captcha.ImageCaptchaQuestion',
    'RecaptchaV2Question': 'woob.capabilities.captcha.RecaptchaV2Question',
    'RecaptchaQuestion': 'woob.capabilities.captcha.RecaptchaQuestion',
    'GeetestV4Question': 'woob.capabilities.captcha.GeetestV4Question',
    'RecaptchaV3Question': 'woob.capabilities.captcha.RecaptchaV3Question',
    'FuncaptchaQuestion': 'woob.capabilities.captcha.FuncaptchaQuestion',
    'HcaptchaQuestion': 'woob.capabilities.captcha.HcaptchaQuestion',
    'TurnstileQuestion': 'woob.capabilities.captcha.TurnstileQuestion',
}


def __getattr__(name: str) -> Exception:
    if name in __deprecated__:
        new_path = __deprecated__[name]
        warnings.warn(
            f"'{name}' is deprecated. Use '{new_path}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        module_name = '.'.join(new_path.split('.')[:-1])
        class_name = new_path.split('.')[-1]
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            raise AttributeError(f"{name} is deprecated, but unable to import {new_path}") from exc

        try:
            return getattr(module, class_name)
        except AttributeError as exc:
            raise AttributeError(f"{name} is deprecated, but unable to import {new_path}") from exc

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__() -> List[str]:
    return sorted(list(__all__) + list(__deprecated__.keys()))
