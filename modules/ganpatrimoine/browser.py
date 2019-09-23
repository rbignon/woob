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
from weboob.browser.exceptions import HTTPNotFound
from weboob.exceptions import ActionNeeded, BrowserIncorrectPassword
from weboob.capabilities.base import empty
from weboob.tools.capabilities.bank.transactions import sorted_transactions

from .pages import (
    LoginPage, HomePage, AccountsPage, AccountDetailsPage, HistoryPage,
)


__all__ = ['GanPatrimoineBrowser']


class GanPatrimoineBrowser(LoginBrowser):
    login = URL(r'https://authentification.(?P<website>.*).fr/cas/login', LoginPage)
    home = URL(r'/front', HomePage)
    accounts = URL(r'/api/ecli/navigation/synthese', AccountsPage)
    account_details = URL(r'/api/v1/contrats/(?P<account_id>.*)', AccountDetailsPage)
    history = URL(r'/api/ecli/vie/historique\?identifiantContrat=(?P<account_id>.*)&epargne=true', HistoryPage)

    def __init__(self, website, *args, **kwargs):
        super(GanPatrimoineBrowser, self).__init__(*args, **kwargs)
        self.website = website
        self.BASEURL = 'https://espaceclient.%s.fr' % website

    def do_login(self):
        self.location(self.BASEURL)
        self.page.login(self.username, self.password)

        if self.login.is_here():
            error_msg = self.page.get_error()
            # Note: these messages are present in the JavaScript on the login page
            messages = {
                'LOGIN_OTP_COMPTE_BLOQUE_TEMPORAIREMENT_MODAL_TITLE': 'Compte bloqué temporairement.',
                'LOGIN_OTP_COMPTE_BLOQUE_TEMPORAIREMENT_MODAL_TEXT': 'Pour des raisons de sécurité, votre compte est temporairement bloqué.',
                'LOGIN_ERREUR_NON_BANQUE_COMPTE_BLOQUE': 'Vous avez saisi trois fois un mot de passe erroné, votre compte est temporairement bloqué.',
                'LOGIN_ERREUR_COMPTE_INACTIF': 'Votre compte client est inactif.'
            }
            if error_msg == 'LOGIN_ERREUR_MOT_PASSE_INVALIDE':
                raise BrowserIncorrectPassword()
            elif error_msg in messages:
                raise ActionNeeded(messages[error_msg])
            assert False, 'Unhandled error at login: %s' % error_msg

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
                    yield card

            elif account._category == 'Epargne bancaire':
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
        if account._category == 'Carte':
            # Card transactions not yet available on the new website
            return

        self.history.go(account_id=account.id.lower())
        # Transactions are sorted by category, not chronologically
        for tr in sorted_transactions(self.page.iter_wealth_history()):
            yield tr
