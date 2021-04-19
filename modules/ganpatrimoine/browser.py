# -*- coding: utf-8 -*-

# Copyright(C) 2012-2021  Budget Insight
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


from weboob.browser import LoginBrowser, URL, need_login
from weboob.capabilities.bank import Account
from weboob.browser.exceptions import HTTPNotFound, ServerError
from weboob.exceptions import (
    BrowserIncorrectPassword, BrowserUnavailable, ActionNeeded,
    AuthMethodNotImplemented,
)
from weboob.capabilities.base import empty
from weboob.tools.capabilities.bank.transactions import sorted_transactions
from weboob.tools.compat import urlparse, parse_qsl

from .pages import (
    LoginPage, HomePage, AccountsPage, AccountDetailsPage, HistoryPage,
    AccountSuperDetailsPage, PortalPage,
)


__all__ = ['GanPatrimoineBrowser']


class GanPatrimoineBrowser(LoginBrowser):
    login = URL(r'https://authentification.(?P<website>.*).fr/auth/realms', LoginPage)
    home = URL(r'/front', HomePage)
    accounts = URL(r'/api/ecli/navigation/synthese', AccountsPage)
    account_details = URL(r'/api/v1/contrats/(?P<account_id>.*)', AccountDetailsPage)
    account_superdetails = URL(r'/api/ecli/vie/contrats/(?P<product_code>.*)-(?P<account_id>.*)', AccountSuperDetailsPage)
    history = URL(r'/api/ecli/vie/historique', HistoryPage)
    portal_page = URL('/wps/myportal/', PortalPage)

    def __init__(self, website, *args, **kwargs):
        super(GanPatrimoineBrowser, self).__init__(*args, **kwargs)
        self.website = website
        self.BASEURL = 'https://espaceclient.%s.fr' % website

    def do_login(self):
        self.location(self.BASEURL)

        # This part is necessary for a child module with a different login URL.
        if not self.login.is_here():
            query = urlparse(self.url).query
            self.login.go(params=parse_qsl(query))

        self.page.login(self.username, self.password)

        if self.login.is_here():
            if self.page.has_strong_authentication():
                # The SMS is sent before we can stop it
                raise AuthMethodNotImplemented()

            error_message = self.page.get_error_message()
            if any((
                'Identifiant ou mot de passe incorrect' in error_message,
                '3 essais infructueux' in error_message,
            )):
                raise BrowserIncorrectPassword(error_message)
            if 'Connexion non autorisée' in error_message:
                raise ActionNeeded(error_message)
            assert False, 'Unhandled error at login: %s' % error_message

    @need_login
    def iter_accounts(self):
        params = {
            'onglet': 'NAV_ONGL_PRIV',
        }
        self.accounts.go(params=params)
        for account in self.page.iter_accounts():
            try:
                self.account_details.go(account_id=account.id.lower())
            except HTTPNotFound:
                # Some accounts have no available detail on the new website,
                # the server then returns a 404 error
                self.logger.warning('No available detail for account n°%s on the new website, it will be skipped.', account.id)
                continue

            # We must deal with different account categories differently
            # because the JSON content depends on the account category.
            if account._category == 'Compte bancaire':
                self.page.fill_account(obj=account)
                # JSON of checking accounts may contain deferred cards
                for card in self.page.iter_cards():
                    card.parent = account
                    card._url = account._url
                    yield card

            elif account._category in ('Epargne bancaire', 'Compte titres', 'Certificat mutualiste'):
                self.page.fill_account(obj=account)

            elif account._category == 'Crédit':
                self.page.fill_loan(obj=account)

            elif account._category in ('Epargne', 'Retraite'):
                self.page.fill_wealth_account(obj=account)

            elif account._category == 'Autre':
                # This category contains PEE and PERP accounts for example.
                # They may contain investments.
                self.page.fill_wealth_account(obj=account)

            else:
                self.logger.warning('Category %s is not handled yet, account n°%s will be skipped.', account._category, account.id)
                continue

            if empty(account.balance):
                try:
                    self.account_superdetails.go(product_code=account._product_code.lower(), account_id=account.id.lower())
                    self.page.fill_account(obj=account)
                except HTTPNotFound:
                    self.logger.warning('No available detail for account n°%s on the new website, it will be skipped.', account.id)
                    continue

            if empty(account.balance):
                self.logger.warning('Could not fetch the balance for account n°%s, it will be skipped.', account.id)
                continue

            yield account

    @need_login
    def iter_investment(self, account):
        if account._category not in ('Epargne', 'Retraite', 'Autre'):
            return

        self.account_details.go(account_id=account.id.lower())
        if self.page.has_investments():
            for inv in self.page.iter_investments():
                yield inv

    @need_login
    def iter_history(self, account):
        param_categories = {
            'Compte bancaire': 'COMPTE_COURANT',
            'Epargne bancaire': 'EPARGNE',
            'Retraite': 'RETRAITE',
            'Epargne': 'EPARGNE',
            'Crédit': 'CREDIT',
            'Carte': 'CARTE',
            'Compte titres': 'COMPTE_TITRES',
            'Certificat mutualiste': 'C_MUTUALISTE',
            'Autre': 'AUTRE',
        }

        if account._category not in param_categories:
            self.logger.warning('History is not yet handled for category %s.', account._category)
            return

        if account._url:
            if account.type != Account.TYPE_CARD:
                self.location(account._url)
                if self.portal_page.is_here():
                    detail_url = self.page.get_account_history_url(account.id)
                    self.location(detail_url, data='')
                    for tr in self.page.iter_history(account_id=account.id):
                        yield tr
        else:

            params = {
                'identifiantContrat': account.id.lower(),
                'familleProduit': param_categories[account._category],
            }
            try:
                self.history.go(params=params)
            except ServerError:
                # Some checking accounts and deferred cards do not have
                # an available history on the new website yet.
                raise BrowserUnavailable()

            # Transactions are sorted by category, not chronologically
            for tr in sorted_transactions(self.page.iter_wealth_history()):
                yield tr

    @need_login
    def iter_coming(self, account):
        if account._url and account.type == Account.TYPE_CARD:
            self.location(account._url)
            if self.portal_page.is_here():
                detail_url = self.page.get_account_history_url(account.id[-6:])
                self.location(detail_url, data='')
                for tr in self.page.iter_card_history():
                    yield tr
