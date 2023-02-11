# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight


from woob.browser import LoginBrowser, URL, need_login
from woob.exceptions import BrowserIncorrectPassword, BrowserUnavailable
from woob.tools.json import json

from .collectivites_pages import (
    ClientSpace, CnicePage, AuraPage, PdfPage, AuthenticationErrorPage,
    ValidatePage, AiguillagePage, RedirectPage, ClientPremiumSpace, MaintenancePage,
)


class EdfproCollectivitesBrowser(LoginBrowser):
    BASEURL = 'https://entreprises-collectivites.edf.fr'

    premium_client_space = URL(r'/espaceclientpremium/s/aiguillage', ClientPremiumSpace)
    client_space = URL(
        r'/espaceclient/s/$',
        r'/espaceclient/s/aiguillage',
        r'/espaces/s/$',
        ClientSpace,
    )
    authentication_error = URL(r'/espaceclient/_nc_external', AuthenticationErrorPage)
    cnice = URL(r'/espace(s|client)/services/authcallback/CNICE', CnicePage)
    aura = URL(r'/espaceclient/s/sfsites/aura', AuraPage)
    premium_aura = URL(r'/espaceclientpremium/s/sfsites/aura', AuraPage)
    download_page = URL(r'/espaceclient/sfc/servlet.shepherd/version/download/(?P<id_download>.*)', PdfPage)
    premium_download_page = URL(r'/espaceclientpremium/sfc/servlet.shepherd/version/download/(?P<id_download>.*)', PdfPage)
    validate_page = URL(r'/espace(s|client)/loginflow/loginFlowOnly.apexp', ValidatePage)
    aiguillage = URL(r'/espace(s|client)/apex/CNICE_VFP234', AiguillagePage)
    redirect = URL(r'/espace(s|client)/CNICE_VFP234_EPIRedirect', RedirectPage)
    maintenance = URL(
        r'/espaceclient/services/auth/sso/CNICE_Maintenance',
        r'https://www.edfentreprises.fr/page_maintenance/index.html',
        MaintenancePage
    )

    def __init__(self, config, *args, **kwargs):
        self.config = config
        kwargs['username'] = self.config['login'].get()
        kwargs['password'] = self.config['password'].get()
        super(EdfproCollectivitesBrowser, self).__init__(*args, **kwargs)
        self.token = None
        self.context = None
        self.is_premium = False

    def do_login(self):
        # here we are already logged, we have been logged in EdfproBrowser, but we have detected a new BASEURL
        # and new pages
        # manually handle response because we were unable to handle it the first time due to another BASEURL
        page = self.client_space.handle(self.response)
        url = page.handle_redirect()
        self.location(url)
        if self.authentication_error.is_here():
            raise BrowserIncorrectPassword(self.page.get_error_message())
        if self.client_space.is_here() and self.page.handle_redirect():
            url = self.page.handle_redirect()
            self.location(url)
        if self.maintenance.is_here():
            raise BrowserUnavailable(self.page.get_message())
        frontdoor_url = self.page.get_frontdoor_url()
        self.location(frontdoor_url)
        self.client_space.go()
        redirect_page = self.page.handle_redirect()
        # sometimes the account is already signed in so we have to disconnect them with redirect url
        if redirect_page:
            limit = 0
            while self.page.handle_redirect() and limit < 5:
                limit += 1
                redirect_page = self.page.handle_redirect()
                self.location(redirect_page)
            if self.premium_client_space.is_here():
                self.is_premium = True
            else:
                self.client_space.go()

        self.token = self.page.get_token()
        aura_config = self.page.get_aura_config()
        self.context = aura_config['context']

    def go_aura(self, message, page_uri=''):
        uri = '/espaceclient/s/%s' % page_uri
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
            'uad': False
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
            "actions":[
                {
                    "id": "894;a",
                    "descriptor": "apex://CNICE_VFC172_DisplayUserProfil/ACTION$getContactInfo",
                    "callingDescriptor": "markup://c:CNICE_LC265_DisplayUserProfil",
                    "params": {}
                }
            ]
        }
        self.go_aura(message, 'historique-factures')
        return self.page.get_subscriber()

    @need_login
    def get_subscription_list(self):
        subscriber = self.get_subscriber()
        message = {
            "actions":[
                {
                    "id": "557;a",
                    "descriptor": "apex://CNICE_VFC151_CompteurListe/ACTION$getCarouselInfos",
                    "callingDescriptor": "markup://c:CNICE_LC218_CompteurListe",
                    "params": {}
                }
            ]
        }
        self.go_aura(message)
        return self.page.iter_subscriptions(subscriber=subscriber)

    @need_login
    def iter_documents(self, subscription):
        message = {
            "actions":[
                {
                    "id": "685;a",
                    "descriptor": "apex://CNICE_VFC158_HistoFactu/ACTION$initializeReglementSolde",
                    "callingDescriptor": "markup://c:CNICE_LC230_HistoFactu",
                    "params": {}
                },
                {
                    "id": "751;a",
                    "descriptor": "apex://CNICE_VFC160_ListeFactures/ACTION$getFacturesbyId",
                    "callingDescriptor": "markup://c:CNICE_LC232_ListeFactures2",
                    "params":
                        {
                            "moeid": subscription._moe_idpe,
                            "originBy": "byMoeIdPE"
                        }
                }
            ]
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
        raise NotImplementedError()
