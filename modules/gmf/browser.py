# Copyright(C) 2017      Tony Malto
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

from woob.browser import LoginBrowser, URL, need_login
from woob.browser.exceptions import ServerError
from woob.exceptions import BrowserIncorrectPassword, ActionNeeded

from .pages import (
    LoginPage, AccountsPage, TransactionsInvestmentsPage, AllTransactionsPage,
    DocumentsSignaturePage, RedirectToUserAgreementPage, UserAgreementPage,
    RedirectionPage, AuthCodePage,
)


class GmfBrowser(LoginBrowser):
    BASEURL = 'https://mon-espace-societaire.gmf.fr'

    login_post = URL(r'/connexion/CAP-US_AccesEC/api/accounts/authentication', LoginPage)
    auth_page = URL(r'https://coveauth.gmf.fr/coveauth-server/oauth2/authorization',)
    redirection_page = URL(r'/homepage\?code=(?P<code>.+)&state=.*', RedirectionPage)
    auth_code_page = URL(r'/cap-mx-espacesocietaire-internet/api/users/authorizationCode', AuthCodePage)

    redirect_to_user_agreement = URL('^$', RedirectToUserAgreementPage)
    user_agreement = URL(r'/restreint/pages/securite/IC9.faces', UserAgreementPage)
    accounts = URL(r'/cap-mx-espacesocietaire-internet/api/prestation', AccountsPage)
    transactions_investments = URL(
        r'https://espace-assure.gmf.fr/pointentree/contratvie/detailsContrats',
        TransactionsInvestmentsPage
    )
    all_transactions = URL(
        r'https://espace-assure.gmf.fr/pages/contratvie/detailscontrats/.*\.faces',
        AllTransactionsPage
    )
    documents_signature = URL(r'/public/pages/authentification/.*\.faces', DocumentsSignaturePage)

    def __init__(self, config, *args, **kwargs):
        kwargs['username'] = config['login'].get()
        kwargs['password'] = config['password'].get()
        super().__init__(*args, **kwargs)
        self.config = config

    def do_login(self):
        try:
            self.login_post.go(
                json={
                    'id': self.username,
                    'motDePasse': self.password,
                },
                params={'marque': 'GMF'}
            )
        except ServerError as e:
            if e.response.status_code == 502:
                # When credentials are incorrect we get a 502 without any error message
                raise BrowserIncorrectPassword()

        status = self.page.get_status()
        if status == 'M':
            raise ActionNeeded(
                '''Pour garantir la sécurité de votre espace client, votre compte nécessite une mise à jour.
                Veuillez vous connecter sur votre portail internet.'''
            )

        id = self.page.get_id()
        self.auth_page.go(
            data={
                'username': id,
                'password': self.password,
                'client_id': 'acces-ec-gmf-PROD',
                'state': 'eyJwIjoiU1RBVEUifQ==',
                'profile': 'accesec',
                'population': '51',
                'ttl': '240',
                'response_type': 'code',
                'redirect_uri': f'{self.BASEURL}/homepage',
            }
        )
        if not self.redirection_page.is_here():
            raise AssertionError('Should be on redirection page')

        # csrf token is needed for accounts page
        code = self.page.params['code']
        self.auth_code_page.go(json={'code': code})
        self.session.headers['covea-csrf-token'] = self.page.get_csrf_token()

    @need_login
    def iter_accounts(self):
        self.accounts.go()
        return self.page.iter_accounts()

    @need_login
    def iter_history(self, account):
        self.accounts.stay_or_go()
        data = self.page.get_details_page_form_data(account)
        self.transactions_investments.go(data=data)
        self.page.show_all_transactions()
        return self.page.iter_history()

    @need_login
    def iter_investment(self, account):
        self.accounts.stay_or_go()
        data = self.page.get_details_page_form_data(account)
        self.transactions_investments.go(data=data)
        if self.page.has_investments():
            return self.page.iter_investments()
        return []
