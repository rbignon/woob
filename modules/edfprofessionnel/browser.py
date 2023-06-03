# Copyright(C) 2016      Jean Walrave
#
# flake8: compatible
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


from woob.browser import LoginBrowser, need_login, URL
from woob.exceptions import (
    BrowserIncorrectPassword, BrowserUnavailable, BrowserUserBanned,
)
from woob.tools.json import json

from .pages import (
    AiguillagePage, AuraPage, AuthenticationErrorPage, AuthPage,
    ClientPremiumSpace, ClientSpace, CnicePage, ErrorPage,
    LoginPage, MaintenancePage, PdfPage, RedirectPage, ValidatePage,
)


class EdfproBrowser(LoginBrowser):
    BASEURL = 'https://entreprises-collectivites.edf.fr'
    AUTH_BASEURL = 'https://auth.entreprises-collectivites.edf.fr'

    login = URL(r'/openam/json/authenticate', LoginPage, base='AUTH_BASEURL')
    auth = URL(
        r'/openam/UI/Login.*',
        r'/ice/rest/aiguillagemp/redirect',
        AuthPage,
        base='AUTH_BASEURL',
    )
    error = URL(r'/page_erreur/', ErrorPage, base='AUTH_BASEURL')
    premium_client_space = URL(
        r'/espaceclientpremium/s/$',
        r'/espaceclientpremium/s/aiguillage',
        r'/espaceclientpremium/secur/frontdoor.jsp',
       ClientPremiumSpace,
    )
    client_space = URL(
        r'/espaceclient/s/$',
        r'/espaceclient/s/aiguillage',
        r'/espaces/secur/frontdoor.jsp',
        r'/espaces/s/$',
        ClientSpace,
    )
    authentication_error = URL(r'/espaceclient/_nc_external', AuthenticationErrorPage)
    cnice = URL(
        r'/espace(s|client(premium)?)/services/authcallback/CNICE',
        r'/espaceclient(premium)?/apex/CNICE',
        r'/espaceclient(premium)?/CNICE_VFP234_EPIRedirect',
        CnicePage
    )
    aura = URL(r'/espaceclient/s/sfsites/aura', AuraPage)
    premium_aura = URL(r'/espaceclientpremium/s/sfsites/aura', AuraPage)
    download_page = URL(r'/espaceclient/sfc/servlet.shepherd/version/download/(?P<id_download>.*)', PdfPage)
    premium_download_page = URL(
        r'/espaceclientpremium/sfc/servlet.shepherd/version/download/(?P<id_download>.*)',
        PdfPage,
    )
    validate_page = URL(r'/espace(s|client)/loginflow/loginFlowOnly.apexp', ValidatePage)
    aiguillage = URL(r'/espace(s|client)/apex/CNICE_VFP234', AiguillagePage)
    redirect = URL(r'/espace(s|client)/CNICE_VFP234_EPIRedirect', RedirectPage)
    maintenance = URL(
        r'/page_maintenance/index.html',
        MaintenancePage,
        base='AUTH_BASEURL',
    )

    def __init__(self, config, *args, **kwargs):
        self.config = config
        kwargs['username'] = self.config['login'].get()
        kwargs['password'] = self.config['password'].get()
        super().__init__(*args, **kwargs)
        self.token = None
        self.context = None
        self.is_premium = False

    def do_login(self):
        # Following all redirections is not mandatory and
        # we need one of the redirections which is the auth_url
        # used several times during the login process
        self.location(
            'https://entreprises-collectivites.edf.fr/espaceclient/services/auth/sso/CNICE',
            params={'startURL': '/espaceclient/s/'},
            allow_redirects=False,
        )

        auth_url = self.response.headers['location']

        # this headers is mandatory to avoid a 403 response code
        headers = {'x-requested-with': 'XMLHttpRequest'}
        params = {
            'realm': '/front_office',
            'goto': auth_url,
        }
        self.login.go(method='POST', params=params, headers=headers)

        login_data = self.page.get_data(self.username, self.password)
        self.login.go(json=login_data, headers=headers)

        error_message = self.page.get_error_message()
        if error_message:
            if 'compte bloqué' in error_message:
                raise BrowserUserBanned(error_message)
            elif 'identifiant ou votre mot de passe est incorrect' in error_message:
                # error_message can't be displayed to the user unless it's filtered through a regexp
                raise BrowserIncorrectPassword('Votre identifiant ou votre mot de passe est incorrect.')
            raise AssertionError(f'Unhandled error during login: {error_message}')

        self.location(auth_url)

        if self.maintenance.is_here():
            raise BrowserUnavailable(self.page.get_message())

        # Not sure if these two exceptions can still happen
        if self.auth.is_here() and self.page.response.status_code != 303:
            self.logger.warning('Old BrowserIncorrectPassword triggered by auth_url')
            raise BrowserIncorrectPassword()

        if self.error.is_here():
            self.logger.warning('Old BrowserUnavailable triggered by auth_url')
            raise BrowserUnavailable(self.page.get_message())

        # Frontdoor URL is on CNICE page
        self.location(
            'https://entreprises-collectivites.edf.fr/espaces/services/auth/sso/CNICE',
            params={'startURL': '/espaces/s/'},
            allow_redirects=True,
        )

        frontdoor_url = self.page.get_frontdoor_url()
        self.location(frontdoor_url)
        redirect_page = self.page.handle_redirect()

        # sometimes the account is already signed in so we have to disconnect them with redirect url
        if redirect_page:
            limit = 0
            while self.page != None and self.page.handle_redirect() and limit < 5:
                limit += 1
                redirect_page = self.page.handle_redirect()
                self.location(redirect_page)

        if self.premium_client_space.is_here():
            self.is_premium = True

        self.token = self.page.get_token()
        aura_config = self.page.get_aura_config()
        self.context = aura_config['context']

    def go_aura(self, message, page_uri=''):
        uri = f'/espaceclient/s/{page_uri}'
        page = self.aura
        if self.is_premium:
            uri = '/espaceclientpremium/s/%s' % page_uri
            page = self.premium_aura

        context = {
            'mode': self.context['mode'],
            'fwuid': self.context['fwuid'],  # this value changes sometimes, (not at every synchronization)
            'app': self.context['app'],
            'loaded': self.context['loaded'],
            'dn': [],
            'globals': {},
            'uad': False,
        }
        data = {
            'aura.pageURI': uri,
            'aura.token': self.token,
            'aura.context': json.dumps(context),
            'message': json.dumps(message),  # message determines kind of response
        }
        page.go(data=data)

    def get_subscriber(self):
        message = {
            'actions': [
                {
                    'id': '894;a',
                    'descriptor': 'apex://CNICE_VFC172_DisplayUserProfil/ACTION$getContactInfo',
                    'callingDescriptor': 'markup://c:CNICE_LC265_DisplayUserProfil',
                    'params': {},
                },
            ],
        }
        self.go_aura(message, 'historique-factures')
        return self.page.get_subscriber()

    @need_login
    def get_subscription_list(self):
        subscriber = self.get_subscriber()
        message = {
            'actions': [
                {
                    'id': '557;a',
                    'descriptor': 'apex://CNICE_VFC151_CompteurListe/ACTION$getCarouselInfos',
                    'callingDescriptor': 'markup://c:CNICE_LC218_CompteurListe',
                    'params': {},
                },
            ],
        }
        self.go_aura(message)
        return self.page.iter_subscriptions(subscriber=subscriber)

    @need_login
    def iter_documents(self, subscription):
        message = {
            'actions': [
                {
                    'id': '685;a',
                    'descriptor': 'apex://CNICE_VFC158_HistoFactu/ACTION$initializeReglementSolde',
                    'callingDescriptor': 'markup://c:CNICE_LC230_HistoFactu',
                    'params': {},
                },
                {
                    'id': '751;a',
                    'descriptor': 'apex://CNICE_VFC160_ListeFactures/ACTION$getFacturesbyId',
                    'callingDescriptor': 'markup://c:CNICE_LC232_ListeFactures2',
                    'params':
                        {
                            'moeid': subscription._moe_idpe,
                            'originBy': 'byMoeIdPE',
                        },
                },
            ],
        }
        self.go_aura(message)
        return sorted(self.page.iter_documents(subid=subscription.id), key=lambda doc: doc.date, reverse=True)

    @need_login
    def download_document(self, document):
        download_page = self.download_page
        if self.is_premium:
            download_page = self.premium_download_page

        self.go_aura(document._message, 'historique-factures')
        id = self.page.get_id_for_download()
        if id:
            # because id seems to be always None
            # when document has been added on website very recently
            download_page.go(id_download=id)
            return self.page.content

    @need_login
    def get_profile(self):
        message = {
            'actions': [
                {
                    'id': '894;a',
                    'descriptor': 'apex://CNICE_VFC172_DisplayUserProfil/ACTION$getContactInfo',
                    'callingDescriptor': 'markup://c:CNICE_LC265_DisplayUserProfil',
                    'params': {},
                },
            ],
        }
        # Get a first json with user information
        self.go_aura(message, 'historique-factures')
        profile = self.page.get_profile()
        message = {
            'actions': [
                {
                    'id': '557;a',
                    'descriptor': 'apex://CNICE_VFC151_CompteurListe/ACTION$getCarouselInfos',
                    'callingDescriptor': 'markup://c:CNICE_LC218_CompteurListe',
                    'params': {},
                },
            ],
        }
        # Get a second json with address information
        self.go_aura(message)
        self.page.fill_profile(obj=profile)
        return profile
