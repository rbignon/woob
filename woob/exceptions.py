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

from __future__ import annotations

import warnings
import importlib

from datetime import datetime
from functools import wraps
from typing import List, Any, Tuple

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
    """The site signals to us our credentials are invalid.

    :type message: str
    :param message: compatibility message for the user (mostly when bad_fields is not given)
    :type bad_fields: list[str]
    :param bad_fields: list of config field names which are incorrect, if it is known
    """

    def __init__(
        self,
        message: str = "",
        bad_fields: List[str] | None = None
    ):
        super().__init__(*filter(None, [message]))
        self.bad_fields = bad_fields


class BrowserForbidden(Exception):
    """The site signals to us that access to a resource is forbidden."""


class BrowserUserBanned(BrowserIncorrectPassword):
    """The site signals to us the user we are logging in as is banned.

    :type message: str
    :param message: compatibility message for the user (mostly when bad_fields is not given)
    :type bad_fields: list[str]
    :param bad_fields: list of config field names which are incorrect, if it is known
    """


class BrowserUnavailable(Exception):
    """The site is either momentarily unavailable, or in maintenance."""


class ScrapingBlocked(BrowserUnavailable):
    """The site has detected scraping, and signals that it has blocked it."""


class BrowserInteraction(Exception):
    """Base class for most browser interactions."""


class BrowserQuestion(BrowserInteraction):
    """The site requires values to be provided by the end user.

    :param fields: The Value objects to be provided by the end user.
    """
    def __init__(self, *fields):
        super().__init__()
        self.fields = fields

    def __str__(self):
        return ", ".join("{}: {}".format(
            field.id or field.label, field.description) for field in self.fields
        )


class OTPQuestion(BrowserQuestion):
    """The site requires transient values to be provided by the end user.

    :param fields: The Value objects to be provided by the end user.
    """


class OTPSentType:
    UNKNOWN = 'unknown'
    SMS = 'sms'
    PHONE_CALL = 'phone_call'
    MOBILE_APP = 'mobile_app'
    EMAIL = 'email'
    DEVICE = 'device'


class SentOTPQuestion(OTPQuestion):
    """A one-time password sent to one of the end user's device is required.

    For example, the site has sent an SMS including a one-time password to a
    phone number associated with the end user, and we need to ask the end
    user to provide this code to us to send it back to the site.

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

    def __init__(
        self,
        field_name: str,
        medium_type: str = OTPSentType.UNKNOWN,
        medium_label: str | None = None,
        message: str = "",
        expires_at: datetime | None = None,
    ):
        super().__init__(Value(field_name, label=message))
        self.message = message
        self.medium_type = medium_type
        self.medium_label = medium_label
        self.expires_at = expires_at


class OfflineOTPQuestion(OTPQuestion):
    """A one-time password generated by the end user is required.

    For example, the site requires a one-time password generated by an
    RFC 6238 compliant application, such as Google Authenticator, to be
    provided, so this exception gets raised to obtain one we can send back
    to the site.

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

    def __init__(
        self,
        field_name: str,
        input: str | None = None,
        medium_label: str | None = None,
        message: str = "",
        expires_at: datetime | None = None
    ):
        super().__init__(Value(field_name, label=message))
        self.input = input
        self.medium_label = medium_label
        self.expires_at = expires_at


class DecoupledMedium:
    UNKNOWN = 'unknown'
    SMS = 'sms'
    MOBILE_APP = 'mobile_app'
    EMAIL = 'email'


class DecoupledValidation(BrowserInteraction):
    """A validation of the current action is requested on a separate channel.

    For example, the site requires the user to click on a link sent in an
    e-mail to pursue logging in on the current session.

    :type medium_type: DecoupledMedium
    :param medium_type: if known, where the decoupled validation was sent
    :type medium_label: str
    :param medium_label: if known, label of where the decoupled validation was
                         sent, e.g. the phone number in case of an app
    :type expires_at: datetime.datetime
    :param expires_at: date when the OTP expires and when replying is too late
    """
    def __init__(
        self,
        message: str = '',
        resource: Any = None,
        medium_type: str = DecoupledMedium.UNKNOWN,
        medium_label: str | None = None,
        expires_at: datetime | None = None,
        *values: Any
    ):
        """
        :param message: message to display to user
        :type message: str
        :param medium_type: if known, where the decoupled validation was sent
        :type medium_type: DecoupledMedium
        :param medium_label: if known, label of where the decoupled validation was sent,
                             e.g. the phone number in case of an app
        :type medium_label: str
        :param expires_at: date when the OTP expires and when replying is too late
        :type expires_at: datetime.datetime
        """
        if values:
            warnings.warn(
                'Variable arguments will be removed in woob 4.',
                DeprecationWarning,
                stacklevel=2
            )
        if resource:
            warnings.warn(
                'The "resource" argument will be removed in woob 4. '
                'Maybe you should inherit this exception class in a '
                'capability to add specific metadata?',
                DeprecationWarning,
                stacklevel=2
            )

        super().__init__(*values)
        self.medium_type = medium_type
        self.medium_label = medium_label
        self.message = message
        self.resource = resource
        self.expires_at = expires_at

    def __str__(self):
        return self.message


class AppValidation(DecoupledValidation):
    """A validation of the current action is requested in a mobile application.

    For example, the site requires the user to open the mobile application
    corresponding to the site, enter a specific password to the application,
    and click on "Validate" for the current operation to be validated.

    :type medium_label: str
    :param medium_label: if known, label of where the decoupled validation was
                         sent, e.g. the phone number in case of an app
    :type expires_at: datetime.datetime
    :param expires_at: date when the OTP expires and when replying is too late
    """

    def __init__(self, *args, **kwargs):
        kwargs['medium_type'] = DecoupledMedium.MOBILE_APP
        super().__init__(*args, **kwargs)


class AppValidationError(Exception):
    """The mobile application validation has failed for a generic reason."""


class AppValidationCancelled(AppValidationError):
    """The mobile application validation has been cancelled.

    This usually happens when the end user has selected "Deny" or "Cancel"
    instead of "Validate" in their mobile application.
    """


class AppValidationExpired(AppValidationError):
    """The mobile application validation has expired.

    This usually happens when the end user hasn't selected any option,
    logged into their mobile application in time to select any option,
    or if they have given up consenting to the operation and the application
    doesn't have a "Deny" option.
    """


class BrowserRedirect(BrowserInteraction):
    """The site requires the end user to do a webauth redirect flow.

    The exception specifies the URL to redirect the user to. At the end
    of the process, i.e. when the end user has been redirected to the
    callback URI with parameters, the 'auth_uri' configuration value should
    be set to the callback URI with parameters for processing by the module.

    :param url: The URL to redirect the end user to.
    :type url: str
    """
    def __init__(
        self,
        url: str,
        resource: Any = None
    ):
        self.url = url

        if resource:
            warnings.warn(
                'The "resource" argument will be removed in woob 4. '
                'Maybe you should inherit this exception class in a '
                'capability to add specific metadata?',
                DeprecationWarning,
                stacklevel=2
            )

        self.resource = resource

    def __str__(self):
        return 'Redirecting to %s' % self.url


class CaptchaQuestion(Exception):
    """The site requires solving a CAPTCHA (base class).

    The response to the captcha should be set, as text, to the
    'captcha_response' configuration value.

    :param type: The type of captcha, as a string.
    """

    # could be improved to pass the name of the backendconfig key
    def __init__(
        self,
        type: str | None = None,
        **kwargs
    ):
        super().__init__('The site requires solving a captcha')
        self.type = type
        for key, value in kwargs.items():
            setattr(self, key, value)


class WrongCaptchaResponse(Exception):
    """The site signals to us that our captcha response is incorrect."""

    def __init__(
        self,
        message: str | None = None
    ):
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


class ModuleInstallError(Exception):
    pass


class ModuleLoadError(Exception):
    def __init__(
        self,
        module_name: str,
        msg: str
    ):
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
    """An action must be performed directly, often on website.

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

    def __init__(
        self,
        message: str | None = None,
        *,
        locale: str | None = None,
        action_type: int | None = None,
        url: str | None = None,
        page: Any = None,
    ):
        args: Tuple[str, ...] = ()
        if message:
            args = (message,)

        super().__init__(*args)
        self.locale = locale
        self.action_type = action_type
        self.page = page
        self.url = url

        if page:
            warnings.warn(
                'ActionNeeded.page is deprecated and will be removed',
                DeprecationWarning,
                stacklevel=2
            )


class AuthMethodNotImplemented(ActionNeeded):
    """Website requires a kind of authentication that is not implemented."""


class BrowserPasswordExpired(ActionNeeded):
    """Credentials are expired, user has to go on website to update them."""


class NeedInteractive(Exception):
    """Require an interactive call by user.

    This may be raised when a method is called by a background job, without a user.
    """


class NeedInteractiveForRedirect(NeedInteractive):
    """Require an interactive call by user to perform a redirect."""


class NeedInteractiveFor2FA(NeedInteractive):
    """Require an interactive call by user to perform a 2FA."""


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
        super().__init__(*args, **kwargs)


__deprecated__ = {
    'ImageCaptchaQuestion': 'woob.capabilities.captcha.ImageCaptchaQuestion',
    'RecaptchaV2Question': 'woob.capabilities.captcha.RecaptchaV2Question',
    'RecaptchaQuestion': 'woob.capabilities.captcha.RecaptchaQuestion',
    'GeetestV4Question': 'woob.capabilities.captcha.GeetestV4Question',
    'RecaptchaV3Question': 'woob.capabilities.captcha.RecaptchaV3Question',
    'FuncaptchaQuestion': 'woob.capabilities.captcha.FuncaptchaQuestion',
    'HcaptchaQuestion': 'woob.capabilities.captcha.HcaptchaQuestion',
    'TurnstileQuestion': 'woob.capabilities.captcha.TurnstileQuestion',
    'NoAccountsException': 'woob.capabilities.bank.NoAccountsException',
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
