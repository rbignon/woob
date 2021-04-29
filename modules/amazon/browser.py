# -*- coding: utf-8 -*-

# Copyright(C) 2017      Théo Dorée
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

from __future__ import unicode_literals

import time
from datetime import date

from woob.browser import LoginBrowser, URL, need_login, StatesMixin
from woob.exceptions import (
    BrowserIncorrectPassword, BrowserUnavailable, ImageCaptchaQuestion, BrowserQuestion,
    WrongCaptchaResponse, NeedInteractiveFor2FA, BrowserPasswordExpired,
    AppValidation, AppValidationExpired, AppValidationCancelled,
)
from woob.tools.value import Value

from .pages import (
    LoginPage, SubscriptionsPage, DocumentsPage, DownloadDocumentPage, HomePage,
    SecurityPage, LanguagePage, HistoryPage, PasswordExpired, ApprovalPage, PollingPage,
    ResetPasswordPage,
)


class AmazonBrowser(LoginBrowser, StatesMixin):
    BASEURL = 'https://www.amazon.fr'
    CURRENCY = 'EUR'
    LANGUAGE = 'fr-FR'

    L_SIGNIN = 'Identifiez-vous'
    L_LOGIN = 'Connexion'
    L_SUBSCRIBER = 'Nom : (.*) Modifier E-mail'

    # The details of the message "L'adresse e-mail est déjà utilisée" are "Il y a un autre compte Amazon
    # avec l'email <email> mais avec un mot de passe différent. L'adresse email a déjà été vérifiée par cet
    # autre compte et seul un compte peut être actif pour une adresse email. Le mot de passe avec lequel vous
    # vous êtes connecté est associé à un compte non vérifié." which tell us there are 2 existing account with
    # the same email address and one of accounts is verified and not the other one and an email address can only
    # be associated to one account which means we are indeed trying to sign in and not to sign up
    WRONGPASS_MESSAGES = [
        "Votre mot de passe est incorrect",
        "Saisissez une adresse e-mail ou un numéro de téléphone portable valable",
        "Impossible de trouver un compte correspondant à cette adresse e-mail",
        "L'adresse e-mail est déjà utilisée",
        "Numéro de téléphone incorrect",
    ]
    WRONG_CAPTCHA_RESPONSE = "Saisissez les caractères tels qu'ils apparaissent sur l'image."

    login = URL(r'/ap/signin(.*)', LoginPage)
    home = URL(r'/$', r'/\?language=.+$', HomePage)
    subscriptions = URL(r'/gp/profile', SubscriptionsPage)
    history = URL(
        r'/gp/your-account/order-history\?ref_=ya_d_c_yo',
        r'/gp/css/order-history\?',
        HistoryPage,
    )
    documents = URL(
        r'/gp/your-account/order-history\?opt=ab&digitalOrders=1(.*)&orderFilter=year-(?P<year>.*)',
        r'/gp/your-account/order-history',
        DocumentsPage,
    )
    download_doc = URL(r'/gp/shared-cs/ajax/invoice/invoice.html', DownloadDocumentPage)
    approval_page = URL(r'/ap/cvf/approval\?', ApprovalPage)
    reset_password_page = URL(r'/ap/forgotpassword/reverification', ResetPasswordPage)
    poll_page = URL(r'/ap/cvf/approval/poll', PollingPage)
    security = URL(
        r'/ap/dcq',
        r'/ap/cvf/',
        r'/ap/mfa',
        SecurityPage,
    )
    language = URL(r'/gp/customer-preferences/save-settings/ref=icp_lop_(?P<language>.*)_tn', LanguagePage)
    password_expired = URL(r'/ap/forgotpassword/reverification', PasswordExpired)

    __states__ = ('otp_form', 'otp_url', 'otp_style', 'otp_headers')

    # According to the cookies we are fine for 1 year after the last sync.
    # If we reset the state every 10 minutes we'll get a in-app validation after 10 minutes
    STATE_DURATION = 60 * 24 * 365

    otp_form = None
    otp_url = None
    otp_style = None
    otp_headers = None

    summary_documents_content = {}

    def __init__(self, config, *args, **kwargs):
        self.config = config
        kwargs['username'] = self.config['email'].get()
        kwargs['password'] = self.config['password'].get()
        super(AmazonBrowser, self).__init__(*args, **kwargs)
        self.previous_url = None

    def locate_browser(self, state):
        if not state['url']:
            return
        if '/ap/cvf/verify' not in state['url'] and not state['url'].endswith('/ap/signin'):
            # don't perform a GET to this url, it's the otp url, which will be reached by otp_form
            # get requests to /ap/signin raise a 404 Client Error
            self.location(state['url'])

    def check_interactive(self):
        if self.config['request_information'].get() is None:
            raise NeedInteractiveFor2FA()

    def send_notification_interactive_mode(self):
        # send app validation if we are in interactive mode
        redirect = self.response.headers.get('Location', "")
        if self.response.status_code == 302 and '/ap/challenge' in redirect:
            self.check_interactive()

        if redirect:
            self.location(self.response.headers['Location'])

    def push_security_otp(self, pin_code):
        res_form = self.otp_form
        res_form['rememberDevice'] = ""

        if self.otp_style == 'amazonDFA':
            res_form['code'] = pin_code
            self.location(self.otp_url, data=res_form, headers=self.otp_headers)
        else:
            res_form['otpCode'] = pin_code
            self.location('/ap/signin', data=res_form, headers=self.otp_headers)

    def handle_security(self):
        if self.config['captcha_response'].get():
            self.page.resolve_captcha(self.config['captcha_response'].get())
            # many captcha, reset value
            self.config['captcha_response'] = Value(value=None)
        else:
            otp_type = self.page.get_otp_type()

            if otp_type == '/ap/signin':
                # this otp will be always present until user deactivate it
                # we don't raise an error because for the seller account 2FA is mandatory
                self.logger.warning('2FA is enabled, all connections send an OTP')

            if self.page.has_form_verify() or self.page.has_form_auth_mfa() or self.page.has_form_select_device():
                self.check_interactive()
                self.page.send_code()
                captcha = self.page.get_captcha_url()

                if captcha and not self.config['captcha_response'].get():
                    image = self.open(captcha).content
                    raise ImageCaptchaQuestion(image)

        if self.page.has_form_verify() or self.page.has_form_auth_mfa():
            form = self.page.get_response_form()
            self.otp_form = form['form']
            self.otp_url = self.url
            self.otp_style = form['style']
            self.otp_headers = dict(self.session.headers)

            raise BrowserQuestion(Value('pin_code', label=self.page.get_otp_message() if self.page.get_otp_message() else 'Please type the OTP you received'))

    def handle_captcha(self, captcha):
        self.otp_form = self.page.get_response_form()
        self.otp_url = self.url
        image = self.open(captcha[0]).content
        raise ImageCaptchaQuestion(image)

    def check_app_validation(self):
        # 25' on website, we don't wait that much, but leave sufficient time for the user
        timeout = time.time() + 600.00
        app_validation_link = self.page.get_link_app_validation()
        polling_request = self.page.get_polling_request()
        approval_status = ''
        while time.time() < timeout:
            self.location(polling_request)
            approval_status = self.page.get_approval_status()

            if approval_status != 'TransactionPending':
                break

            # poll every 5 seconds on website
            time.sleep(5)

        else:
            raise AppValidationExpired()

        if approval_status in ['TransactionCompleted', 'TransactionResponded']:
            self.location(app_validation_link)

            if self.reset_password_page.is_here():
                raise AppValidationCancelled()

            if self.approval_page.is_here():
                raise AssertionError('The validation was not effective for an unknown reason.')

        elif approval_status == 'TransactionCompletionTimeout':
            raise AppValidationExpired()

        else:
            raise AssertionError('Unknown transaction status: %s' % approval_status)

    def do_login(self):
        if self.config['pin_code'].get():
            # Resolve pin_code
            self.push_security_otp(self.config['pin_code'].get())

            if self.security.is_here() or self.login.is_here():
                # Something went wrong, probably a wrong OTP code
                raise BrowserIncorrectPassword('OTP incorrect')
            else:
                # Means security was passed, we're logged
                return

        if self.config['resume'].get():
            self.check_app_validation()
            # we are logged
            return

        if self.security.is_here():
            self.handle_security()

        if self.config['captcha_response'].get():
            # Resolve captcha code
            self.page.login(self.username, self.password, self.config['captcha_response'].get())
            self.send_notification_interactive_mode()
            # many captcha reset value
            self.config['captcha_response'] = Value(value=None)

            if self.security.is_here():
                # Raise security management
                self.handle_security()

            if self.login.is_here():
                msg = self.page.get_error_message()

                if any(wrongpass_message in msg for wrongpass_message in self.WRONGPASS_MESSAGES):
                    raise BrowserIncorrectPassword(msg)
                elif self.WRONG_CAPTCHA_RESPONSE in msg:
                    raise WrongCaptchaResponse(msg)
                else:
                    assert False, msg

        if self.approval_page.is_here():
            # if we have captcha and app validation
            msg_validation = self.page.get_msg_app_validation()
            raise AppValidation(msg_validation)

        # Change language so everything is handled the same way
        self.to_english(self.LANGUAGE)

        # To see if we're connected. If not, we land on LoginPage
        # We need to try previous_url first since sometime we can access the history page without being
        # redirected to the login page while previous_url is redirected
        if self.previous_url:
            self.previous_url.go()
        else:
            self.history.go()

        if not self.login.is_here():
            return

        self.page.login(self.username, self.password)
        self.send_notification_interactive_mode()

        if self.approval_page.is_here():
            # if we don't have captcha and we have app validation
            msg_validation = self.page.get_msg_app_validation()
            raise AppValidation(msg_validation)

        if self.password_expired.is_here():
            raise BrowserPasswordExpired(self.page.get_message())

        if self.security.is_here():
            # Raise security management
            self.handle_security()

        if self.login.is_here():
            captcha = self.page.has_captcha()
            if captcha and not self.config['captcha_response'].get():
                self.handle_captcha(captcha)
            else:
                msg = self.page.get_error_message()
                assert any(wrongpass_message in msg for wrongpass_message in self.WRONGPASS_MESSAGES), msg
                raise BrowserIncorrectPassword(msg)

        if self.reset_password_page.is_here():
            raise BrowserPasswordExpired(self.page.get_message())

    def is_login(self):
        if self.login.is_here():
            self.do_login()
        else:
            if self.approval_page.is_here():
                self.check_interactive()
                self.check_app_validation()
                return
            raise BrowserUnavailable()

    def to_english(self, language):
        # We put language in english
        datas = {
            '_url': '/?language=' + language.replace('-', '_'),
            'LOP': language.replace('-', '_'),
        }
        self.language.go(method='POST', data=datas, language=language)

    @need_login
    def iter_subscription(self):
        self.subscriptions.go()

        if not self.subscriptions.is_here():
            self.previous_url = self.subscriptions
            self.is_login()
            self.previous_url = None

        yield self.page.get_item()

    @need_login
    def iter_documents(self, subscription):
        self.history.go()
        b2b_group_key = self.page.get_b2b_group_key()

        if b2b_group_key:
            # this value is available for business account only
            params = {
                'opt': 'ab',
                'digitalOrders': 1,
                'unifiedOrders': 1,
                'selectedB2BGroupKey': b2b_group_key
            }
            # we select the page where we can find documents from every payers, not just 'myself'
            self.location('/gp/your-account/order-history/ref=b2b_yo_dd_oma', params=params)
            _, group_key = b2b_group_key.split(':')
            # we need this to get bills when this is amazon business, else html page won't contain them
            params = {'selectedB2BGroupKey': group_key}
        else:
            params = {}

        year = date.today().year
        old_year = year - 2
        while year >= old_year:
            self.documents.go(year=year, params=params)
            request_id = self.page.response.headers['x-amz-rid']
            for doc in self.page.iter_documents(subid=subscription.id, currency=self.CURRENCY, request_id=request_id):
                yield doc

            year -= 1
