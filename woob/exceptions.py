# -*- coding: utf-8 -*-

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

from woob.tools.value import Value


class BrowserIncorrectPassword(Exception):
    def __init__(self, message="", bad_fields=None):
        """
        :type message: str
        :param message: compatibility message for the user (mostly when bad_fields is not given)
        :type bad_fields: list[str]
        :param bad_fields: list of config field names which are incorrect, if it is known
        """

        super(BrowserIncorrectPassword, self).__init__(*filter(None, [message]))
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

        super(SentOTPQuestion, self).__init__(Value(field_name, label=message))


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

        super(OfflineOTPQuestion, self).__init__(Value(field_name, label=message))
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

        super(DecoupledValidation, self).__init__(*values)
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
        super(AppValidation, self).__init__(*args, **kwargs)


class AppValidationError(Exception):
    def __init__(self, message=''):
        super(AppValidationError, self).__init__(message)


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
        super(CaptchaQuestion, self).__init__("The site requires solving a captcha")
        self.type = type
        for key, value in kwargs.items():
            setattr(self, key, value)


class WrongCaptchaResponse(Exception):
    """when website tell us captcha response is not good"""
    def __init__(self, message=None):
        super(WrongCaptchaResponse, self).__init__(message or "Captcha response is wrong")


class ImageCaptchaQuestion(CaptchaQuestion):
    type = 'image_captcha'

    image_data = None

    def __init__(self, image_data):
        super(ImageCaptchaQuestion, self).__init__(self.type, image_data=image_data)


class RecaptchaV2Question(CaptchaQuestion):
    type = 'g_recaptcha'

    website_key = None
    website_url = None

    def __init__(self, website_key, website_url):
        super(RecaptchaV2Question, self).__init__(self.type, website_key=website_key, website_url=website_url)


class RecaptchaQuestion(CaptchaQuestion):
    type = 'g_recaptcha'

    website_key = None
    website_url = None

    def __init__(self, website_key, website_url):
        super(RecaptchaQuestion, self).__init__(self.type, website_key=website_key, website_url=website_url)


class GeetestV4Question(CaptchaQuestion):
    type = 'GeeTestTaskProxyless'

    website_url = None
    gt = None

    def __init__(self, website_url, gt):
        super().__init__(self.type, website_url=website_url, gt=gt)

class RecaptchaV3Question(CaptchaQuestion):
    type = 'g_recaptcha'

    website_key = None
    website_url = None
    action = None
    min_score = None
    is_enterprise = False

    def __init__(self, website_key, website_url, action=None, min_score=None, is_enterprise=False):
        super(RecaptchaV3Question, self).__init__(self.type, website_key=website_key, website_url=website_url)
        self.action = action
        self.min_score = min_score
        self.is_enterprise = is_enterprise


class FuncaptchaQuestion(CaptchaQuestion):
    type = 'funcaptcha'

    website_key = None
    website_url = None
    sub_domain = None

    data = None
    """Optional additional data, as a dictionary.

    For example, a site could transmit a 'blob' property which you should
    get, and transmit as {'blob': your_blob_value} through this property.
    """

    def __init__(self, website_key, website_url, sub_domain=None, data=None):
        super().__init__(
            self.type,
            website_key=website_key,
            website_url=website_url,
            sub_domain=sub_domain,
            data=data,
        )


class HcaptchaQuestion(CaptchaQuestion):
    type = 'hcaptcha'

    website_key = None
    website_url = None

    def __init__(self, website_key, website_url):
        super(HcaptchaQuestion, self).__init__(self.type, website_key=website_key, website_url=website_url)


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
        super(ModuleLoadError, self).__init__(msg)
        self.module = module_name


class ActionType(object):
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
