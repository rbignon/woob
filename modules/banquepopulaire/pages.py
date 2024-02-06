# Copyright(C) 2012 Romain Bignon
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

import re
from io import BytesIO

from PIL import Image, ImageFilter

from woob.browser.filters.html import Attr, Link
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    CleanText, Coalesce, Regexp,
)
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, RawPage, XMLPage
from woob.capabilities import NotAvailable
from woob.exceptions import BrowserIncorrectPassword, BrowserUnavailable
from woob.tools.captcha.virtkeyboard import SplitKeyboard
from woob_modules.caissedepargne.pages import (
    AuthenticationMethodPage as _AuthenticationMethodPage,
    JsFilePage as _JsFilePage,
    LoginTokensPage as _LoginTokensPage,
)

class LoggedOut(Exception):
    pass

class BrokenPageError(Exception):
    pass

class BasePage(object):
    ENCODING = 'iso-8859-15'

    def is_error(self):
        for script in self.doc.xpath('//script'):
            if script.text is not None and (
                "Le service est momentanément indisponible" in script.text
                or "Le service est temporairement indisponible" in script.text
                or "Votre abonnement ne vous permet pas d'accéder à ces services" in script.text
                or 'Merci de bien vouloir nous en excuser' in script.text
            ):
                return True

        # sometimes the doc is a broken xhtml that fails to be parsed correctly
        if "Ressource indisponible" in self.text and "Le service est momentan&#233ment indisponible" in self.text:
            return True

        if "Ressource interdite" in self.text and "Vous ne pouvez acc&#233der &#224 cette page" in self.text:
            return True

        return False

class MyHTMLPage(BasePage, HTMLPage):
    def build_doc(self, data, *args, **kwargs):
        # XXX FUCKING HACK BECAUSE BANQUE POPULAIRE ARE NASTY AND INCLUDE NULL
        # BYTES IN DOCUMENTS.
        data = data.replace(b'\x00', b'')
        return super(MyHTMLPage, self).build_doc(data, *args, **kwargs)

class RedirectErrorPage(HTMLPage):
    def is_unavailable(self):
        return bool(CleanText('//p[contains(text(), "momentanément indisponible")]')(self.doc))

class AuthorizeErrorPage(HTMLPage):
    def is_here(self):
        return CleanText('//p[contains(text(), "momentanément indisponible")]')(self.doc)

    def get_error_message(self):
        return CleanText('//p[contains(text(), "momentanément indisponible")]')(self.doc)

class ErrorPage(LoggedPage, MyHTMLPage):
    def on_load(self):
        if CleanText('//pre[contains(text(), "unexpected error")]')(self.doc):
            raise BrowserUnavailable('An unexpected error has occured.')
        if CleanText('//script[contains(text(), "momentanément indisponible")]')(self.doc):
            raise BrowserUnavailable("Le service est momentanément indisponible")
        elif CleanText('//h1[contains(text(), "Cette page est indisponible")]')(self.doc):
            raise BrowserUnavailable('Cette page est indisponible')
        return super(ErrorPage, self).on_load()

    def get_token(self):
        try:
            buf = self.doc.xpath('//body/@onload')[0]
        except IndexError:
            return
        else:
            m = re.search(r"saveToken\('([^']+)'\)", buf)
            if m:
                return m.group(1)

class UnavailablePage(LoggedPage, MyHTMLPage):
    def on_load(self):
        h1 = CleanText('//h1[1]')(self.doc)
        if "est indisponible" in h1:
            raise BrowserUnavailable(h1)
        body = CleanText(".")(self.doc)
        if "An unexpected error has occurred." in body or "Une erreur s'est produite" in body:
            raise BrowserUnavailable(body)

        a = Link('//a[@class="btn"][1]', default=None)(self.doc)
        if not a:
            raise BrowserUnavailable()
        self.browser.location(a)

class NewLoginPage(HTMLPage):
    def get_main_js_file_url(self):
        return Attr('//script[contains(@src, "main.")]', 'src')(self.doc)

class JsFilePage(_JsFilePage):
    def get_client_id(self):
        return Regexp(pattern=r'{authenticated:{clientId:"([^"]+)"').filter(self.text)

    def get_user_info_client_id(self):
        return Regexp(pattern=r'anonymous:{clientId:"([^"]+)"').filter(self.text)
    
class JsFilePageEspaceClient(_JsFilePage):
    def get_client_id(self):
        return Regexp(pattern=r'pasConfig:{authenticatedGatewayThreeLeggedAuthenticationAsUrl:Pe,clientId:"([^"]+)"').filter(self.text)

    def get_user_info_client_id(self):
        return Regexp(pattern=r'{clientCredentialConfig:{clientId:"([^"]+)"').filter(self.text)

class SynthesePage(JsonPage):
    def get_raw_json(self):
        return self.text
    
class TransactionPage(JsonPage):
    def get_raw_json(self):
        return self.text

class AuthorizePage(JsonPage):
    def build_doc(self, content):
        # Sometimes we end up on this page but no
        # response body is given, so we get a decode error.
        # handle this page can assure the continuity of the login
        try:
            return super(AuthorizePage, self).build_doc(content)
        except ValueError:
            return {}

    def get_next_url(self):
        return Dict('action')(self.doc)

    def get_payload(self):
        return Dict('parameters/SAMLRequest')(self.doc)

class LoginTokensPage(_LoginTokensPage):
    #def get_expires_in(self):
    #    return Dict('parameters/expires_in')(self.doc)

    def get_access_token(self):
        return Dict('parameters/access_token', default=None)(self.doc)
    
    def get_access_expire(self):
        return Dict('parameters/expires_in', default=None)(self.doc)

class InfoTokensPage(JsonPage):
    pass

class AuthenticationMethodPage(_AuthenticationMethodPage):
    def get_next_url(self):
        return Dict('response/saml2_post/action')(self.doc)

    def get_payload(self):
        return Dict('response/saml2_post/samlResponse', default=NotAvailable)(self.doc)

    def is_new_login(self):
        # We check here if we are doing a new login
        return bool(Dict('step/phase/state', default=NotAvailable)(self.doc))

    def get_status(self):
        return Dict('response/status', default=NotAvailable)(self.doc)

    def get_security_level(self):
        return Dict('step/phase/securityLevel', default='')(self.doc)

    def get_error_msg(self):
        return Coalesce(
            Dict('phase/notifications/0', default=None),
            Dict('phase/previousResult', default=None),
            Dict('response/status', default=None),
            default=None
        )(self.doc)

    def login_errors(self, error, otp_type=None):
        """Adapted from caissedepargne: better handle wrong OTPs"""
        if error is None:
            # If the authentication failed, we don't have a status in the response
            error_msg = self.get_error_msg()
            if error_msg:
                if otp_type is not None:
                    if 'otp_sms_invalid' in error_msg and otp_type == 'SMS':
                        raise BrowserIncorrectPassword('Code SMS erroné')
                    if 'FAILED_AUTHENTICATION' in error_msg and otp_type == 'EMV':
                        raise BrowserIncorrectPassword("Code d'authentification erroné")
                raise AssertionError('Unhandled error message: %s' % error_msg)

        return super().login_errors(error)


class AuthenticationStepPage(AuthenticationMethodPage):
    def get_status(self):
        return Coalesce(
            Dict('response/status', default=NotAvailable),
            Dict('phase/state', default=NotAvailable)
        )(self.doc)

    def get_next_url(self):
        return Dict('response/saml2_post/action')(self.doc)

    def get_payload(self):
        return Dict('response/saml2_post/samlResponse')(self.doc)

    def get_phone_number(self):
        return Dict(f'validationUnits/0/{self.validation_unit_id}/0/phoneNumber')(self.doc)

    def get_devices(self):
        return Dict(f'validationUnits/0/{self.validation_unit_id}/0/devices')(self.doc)

    def get_time_left(self):
        return Dict(f'validationUnits/0/{self.validation_unit_id}/0/requestTimeToLive')(self.doc)

    def authentication_status(self):
        return Dict('response/status', default=None)(self.doc)

    def is_authentication_successful(self):
        return Dict('response/status', default=None)(self.doc) == "AUTHENTICATION_SUCCESS"


class AppValidationPage(XMLPage):
    def get_status(self):
        return CleanText('//response/status')(self.doc)

class LoginPage(MyHTMLPage):
    def on_load(self):
        h1 = CleanText('//h1[1]')(self.doc)

        if h1.startswith('Le service est moment'):
            text = CleanText('//h4[1]')(self.doc) or h1
            raise BrowserUnavailable(text)

        if not self.browser.no_login:
            raise LoggedOut()

class BPOVirtKeyboard(SplitKeyboard):
    char_to_hash = {
        '0': '66ec79b200706e7f9c14f2b6d35dbb05',
        '1': ('529819241cce382b429b4624cb019b56', '0ea8c08e52d992a28aa26043ffc7c044'),
        '2': 'fab68678204198b794ce580015c8637f',
        '3': '3fc5280d17cf057d1c4b58e4f442ceb8',
        '4': (
            'dea8800bdd5fcaee1903a2b097fbdef0', 'e413098a4d69a92d08ccae226cea9267',
            '61f720966ccac6c0f4035fec55f61fe6', '2cbd19a4b01c54b82483f0a7a61c88a1',
        ),
        '5': 'ff1909c3b256e7ab9ed0d4805bdbc450',
        '6': '7b014507ffb92a80f7f0534a3af39eaa',
        '7': '7d598ff47a5607022cab932c6ad7bc5b',
        '8': ('4ed28045e63fa30550f7889a18cdbd81', '88944bdbef2e0a49be9e0c918dd4be64'),
        '9': 'dd6317eadb5a0c68f1938cec21b05ebe',
    }
    codesep = ' '

    def __init__(self, browser, images):
        code_to_filedata = {}
        for img_item in images:
            img_content = browser.location(img_item['uri']).content
            img = Image.open(BytesIO(img_content))
            img = img.filter(ImageFilter.UnsharpMask(
                radius=2,
                percent=150,
                threshold=3,
            ))
            img = img.convert('L', dither=None)

            def threshold_func(x):
                if x < 20:
                    return 0
                return 255

            img = Image.eval(img, threshold_func)
            b = BytesIO()
            img.save(b, format='PNG')
            code_to_filedata[img_item['value']] = b.getvalue()
        super(BPOVirtKeyboard, self).__init__(code_to_filedata)

class HomePage(LoggedPage, MyHTMLPage):
    # Sometimes, the page is empty but nothing is scrapped on it.
    def build_doc(self, data, *args, **kwargs):
        if not data:
            return None
        return super(MyHTMLPage, self).build_doc(data, *args, **kwargs)

class AccountsPage(LoggedPage, MyHTMLPage):
    pass

class LastConnectPage(LoggedPage, RawPage):
    pass
