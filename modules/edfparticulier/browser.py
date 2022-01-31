# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
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

from __future__ import unicode_literals

from time import time

from woob.browser import LoginBrowser, URL, need_login, StatesMixin
from woob.exceptions import BrowserIncorrectPassword, BrowserQuestion, NeedInteractiveFor2FA
from woob.tools.antibot.akamai import AkamaiMixin
from woob.tools.compat import unquote
from woob.tools.decorators import retry
from woob.tools.json import json
from woob.tools.value import Value

from .pages import (
    HomePage, AuthenticatePage, AuthorizePage, WrongPasswordPage, CheckAuthenticatePage, ProfilPage,
    DocumentsPage, WelcomePage, UnLoggedPage, ProfilePage, BillDownload, XUIPage, OTPTemplatePage,
)


class BrokenPageError(Exception):
    pass


class EdfParticulierBrowser(LoginBrowser, StatesMixin, AkamaiMixin):
    BASEURL = 'https://particulier.edf.fr'

    home = URL('/fr/accueil/contrat-et-conso/mon-compte-edf.html', HomePage)
    xuipage = URL(r'https://espace-client.edf.fr/sso/XUI/#login/&realm=(?P<realm>.*)&goto=(?P<goto>.*)', XUIPage)
    authenticate = URL(r'https://espace-client.edf.fr/sso/json/authenticate', AuthenticatePage)

    otp_template = URL(r'https://espace-client.edf.fr/sso/XUI/templates/openam/authn/HOTPcust4.html', OTPTemplatePage)

    authorize = URL(r'https://espace-client.edf.fr/sso/oauth2/INTERNET/authorize', AuthorizePage)
    wrong_password = URL(
        r'https://espace-client.edf.fr/sso/XUI/templates/openam/authn/PasswordAuth2.html',
        WrongPasswordPage
    )
    check_authenticate = URL('/services/rest/openid/checkAuthenticate', CheckAuthenticatePage)
    user_status = URL('/services/rest/checkuserstatus/getUserStatus')
    not_connected = URL('/fr/accueil/connexion/mon-espace-client.html', UnLoggedPage)
    connected = URL('/fr/accueil/espace-client/tableau-de-bord.html', WelcomePage)
    profil = URL('/services/rest/authenticate/getListContracts', ProfilPage)
    csrf_token = URL(r'/services/rest/init/initPage\?_=(?P<timestamp>.*)', ProfilPage)
    documents = URL('/services/rest/edoc/getMyDocuments', DocumentsPage)
    bills = URL('/services/rest/edoc/getBillsDocuments', DocumentsPage)
    bill_informations = URL('/services/rest/document/dataUserDocumentGetX', DocumentsPage)
    bill_download = URL(
        r'/services/rest/document/getDocumentGetXByData\?csrfToken=(?P<csrf_token>.*)&dn=(?P<dn>.*)&pn=(?P<pn>.*)&di=(?P<di>.*)&bn=(?P<bn>.*)&an=(?P<an>.*)',
        BillDownload
    )
    profile = URL('/services/rest/context/getCustomerContext', ProfilePage)

    __states__ = ('id_token1', 'otp_data')

    def __init__(self, config, *args, **kwargs):
        self.config = config
        self.otp_data = None
        self.id_token1 = None
        kwargs['username'] = self.config['login'].get()
        kwargs['password'] = self.config['password'].get()
        super(EdfParticulierBrowser, self).__init__(*args, **kwargs)

    def locate_browser(self, state):
        pass

    def do_login(self):
        # ********** admire how login works on edf par website **********
        # login part on edf particulier website is very tricky
        # FIRST time we connect we have an otp, BUT not password, we can't know if it is wrong at this moment
        # SECOND time we use password, and not otp
        auth_params = {'realm': '/INTERNET'}

        if self.config['otp'].get():
            self.otp_data['callbacks'][0]['input'][0]['value'] = self.config['otp'].get()
            headers = {
                'X-Requested-With': 'XMLHttpRequest',
            }
            self.authenticate.go(json=self.otp_data, params=auth_params, headers=headers)
            output = self.page.get_data()['callbacks'][1]['output'][0]

            if output['name'] == 'prompt':
                self.id_token1 = output['value']
                # id_token1 is VERY important, we keep it indefinitely, without it edf will ask again otp
            elif output['name'] == 'message':
                assert output['value'] == 'Code incorrect', output['value']
                raise BrowserIncorrectPassword(output['value'])
            else:
                raise AssertionError(output['name'])
        else:
            self.connected.go()
            if self.connected.is_here():
                # we are already logged
                # sometimes even if password is wrong, you can be logged if you retry
                self.logger.info('already logged')
                return

            if not self.xuipage.is_here():
                raise AssertionError('Wrong workflow - authentication has changed, please report error')

            auth_params['goto'] = goto = self.page.params.get('goto', '')
            self.session.cookies.clear()

            akamai_url = self.page.get_akamai_url()
            akamai_solver = self.get_akamai_solver(akamai_url, self.url)
            cookie_abck = self.session.cookies['_abck']
            self.post_sensor_data(akamai_solver, cookie_abck)

            cookie_abck = self.session.cookies['_abck']
            self.post_sensor_data(akamai_solver, cookie_abck)

            self.authenticate.go(method='POST', params=auth_params, data='')
            data = self.page.get_data()
            data['callbacks'][0]['input'][0]['value'] = self.username

            # yes, realm param is present twice
            auth_params = [('realm', '/INTERNET'), ('realm', '/INTERNET'), ('goto', unquote(goto))]
            self.authenticate.go(json=data, params=auth_params)
            data = self.page.get_data()  # yes, we have to get response and send it again, beautiful isn't it ?
            if data['stage'] == 'UsernameAuth2':
                # username is wrong
                raise BrowserIncorrectPassword(data['callbacks'][1]['output'][0]['value'])

            if self.id_token1:
                data['callbacks'][0]['input'][0]['value'] = self.id_token1
            else:
                # the FIRST time we connect, we don't have id_token1, we have no choice, we'll receive an otp
                data['callbacks'][0]['input'][0]['value'] = ' '

            self.authenticate.go(json=data, params=auth_params)
            data = self.page.get_data()

            assert data['stage'] in ('HOTPcust3', 'PasswordAuth2'), 'stage is %s' % data['stage']

            if data['stage'] == 'HOTPcust3':  # OTP part
                self.check_interactive()
                if self.id_token1:
                    # this shouldn't happen except if id_token1 expire one day, who knows...
                    self.logger.warning('id_token1 is not null but edf ask again for otp')

                # a legend say this url is the answer to life the universe and everything, because it is use EVERYWHERE in login
                self.authenticate.go(json=self.page.get_data(), params=auth_params)
                self.otp_data = self.page.get_data()
                # There are three ways to get a message for the otp:
                # 1: Get the message from self.otp_data['callbacks'][0]['output'][0]['value'] to get "Enter OTP"
                # 2: Get the message from self.otp_data['header'] to get "Veuillez saisir le code OTP.
                # Un code OTP va etre envoye suivant les moyens d'authentification pre-definis (SMS et/ou Email)"
                # (ascii only)
                # 3: Get the message from a template page to get "Un code a été envoyé" then append the method
                # used to send the otp to get something like "Un code a été envoyé (à|au) <email|number>"
                otp_device = self.otp_data['callbacks'][3]['output'][0]['value']
                self.otp_template.go()
                label = self.page.get_otp_message()
                # It's done like this in the JavaScript to tell if we put "au <number>"  or "à <email>"
                if '@' in otp_device:
                    label += ' à %s' % otp_device
                else:
                    label += ' au %s' % otp_device
                raise BrowserQuestion(Value('otp', label=label))

            if data['stage'] == 'PasswordAuth2':  # password part
                data['callbacks'][0]['input'][0]['value'] = self.password
                self.authenticate.go(json=self.page.get_data(), params=auth_params)

                # should be SetPasAuth2 if password is ok
                if self.page.get_data()['stage'] == 'PasswordAuth2':
                    attempt_number = int(self.page.get_data()['callbacks'][1]['output'][0]['value'])
                    # attempt_number is the number of wrong password that remains before blocking
                    msg = self.wrong_password.go().get_wrongpass_message(attempt_number)
                    raise BrowserIncorrectPassword(msg)

        data = self.page.get_data()
        # yes, send previous data again, i know i know
        self.authenticate.go(json=data, params=auth_params)
        self.session.cookies['ivoiream'] = self.page.get_token()
        self.user_status.go()

        """
        call check_authenticate url before get subscription in profile, or we'll get an error 'invalid session'
        we do nothing with this response (which contains false btw)
        but edf website expect we call it before or will reject us
        """
        self.check_authenticate.go()

    def check_interactive(self):
        if self.config['request_information'].get() is None:
            raise NeedInteractiveFor2FA()

    def get_csrf_token(self):
        return self.csrf_token.go(timestamp=int(time())).get_token()

    @need_login
    def get_subscription_list(self):
        return self.profil.stay_or_go().iter_subscriptions()

    @need_login
    def iter_documents(self, subscription):
        self.documents.go()  # go to docs before, else we get an error, thanks EDF

        return self.bills.go().iter_bills(subid=subscription.id)

    @retry(BrokenPageError, tries=2, delay=4)
    @need_login
    def download_document(self, document):
        token = self.get_csrf_token()

        data = {
            'bpNumber': document._bp,
            'csrfToken': token,
            'docId': document._doc_number,
            'docName': 'FACTURE',
            'numAcc': document._num_acc,
            'parNumber': document._par_number,
        }

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'Accept': 'application/json, text/plain, */*',
        }
        self.bill_informations.go(headers=headers, data=json.dumps(data))
        bills_informations = self.page.get_bills_informations()

        self.bill_download.go(
            csrf_token=token,
            dn='FACTURE',
            pn=document._par_number,
            di=document._doc_number,
            bn=bills_informations.get('bpNumber'),
            an=bills_informations.get('numAcc')
        )

        # sometimes we land to another page that tell us, this document doesn't exist, but just sometimes...
        # make sure this page is the right one to avoid return a html page as document
        if not self.bill_download.is_here():
            raise BrokenPageError()
        return self.page.content

    @need_login
    def get_profile(self):
        self.profile.go()
        return self.page.get_profile()
