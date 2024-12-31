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
import time
from collections import Counter
from fnmatch import fnmatch
from urllib.parse import urlparse

from requests import HTTPError, TooManyRedirects

from woob.browser import need_login
from woob.browser.exceptions import ClientError
from woob.browser.url import URL
from woob.capabilities.base import find_object
from woob.exceptions import BrowserIncorrectPassword, BrowserUnavailable
from woob.tools.capabilities.bank.transactions import (
    keep_only_card_transactions, omit_deferred_transactions, sorted_transactions,
)
from woob.tools.json import json
from woob_modules.linebourse.browser import LinebourseAPIBrowser

from ..browser import CaisseEpargneLogin
from .pages import (
    CenetAccountHistoryPage, CenetAccountsPage, CenetCardsPage, CenetCardSummaryPage, CenetHomePage, CenetLoanPage,
    CenetLoginPage, DownloadDocumentPage, LinebourseTokenPage, SubscriptionPage,
)


__all__ = ['CenetBrowser']


class CenetBrowser(CaisseEpargneLogin):
    BASEURL = "https://www.cenet.caisse-epargne.fr"

    SKIP_LOCATE_BROWSER_ON_CONFIG_VALUES = ('otp_sms',)
    STATE_DURATION = 5

    cenet_new_home = CaisseEpargneLogin.home_page.with_urls(
        r'https://www.caisse-epargne.fr/espace-entreprise/web-b2b/callback'
    )

    js_file = CaisseEpargneLogin.js_file.with_urls(
        r'https://www.caisse-epargne.fr/espace-entreprise/web-b2b/(?P<js_file_name>[^/]+)',
        clear=False,
    )

    cenet_vk = URL(r'https://www.cenet.caisse-epargne.fr/Web/Api/ApiAuthentification.asmx/ChargerClavierVirtuel')
    cenet_home = URL(
        r'/Default.aspx$',
        r'/default.aspx$',
        CenetHomePage
    )
    cenet_accounts = URL(r'/Web/Api/ApiComptes.asmx/ChargerSyntheseComptes', CenetAccountsPage)
    cenet_market_accounts = URL(r'/Web/Api/ApiBourse.asmx/ChargerComptesTitres', CenetAccountsPage)
    cenet_loans = URL(r'/Web/Api/ApiFinancements.asmx/ChargerListeFinancementsMLT', CenetLoanPage)
    cenet_account_history = URL(r'/Web/Api/ApiComptes.asmx/ChargerHistoriqueCompte', CenetAccountHistoryPage)
    cenet_account_coming = URL(r'/Web/Api/ApiCartesBanquaires.asmx/ChargerEnCoursCarte', CenetAccountHistoryPage)
    cenet_tr_detail = URL(r'/Web/Api/ApiComptes.asmx/ChargerDetailOperation', CenetCardSummaryPage)
    cenet_cards = URL(r'/Web/Api/ApiCartesBanquaires.asmx/ChargerCartes', CenetCardsPage)
    cenet_login = URL(
        r'https://.*/$',
        r'https://.*/default.aspx',
        CenetLoginPage,
    )
    linebourse_token = URL(r'/Web/Api/ApiBourse.asmx/GenererJeton', LinebourseTokenPage)

    subscription = URL(r'/Web/Api/ApiReleves.asmx/ChargerListeEtablissements', SubscriptionPage)
    documents = URL(r'/Web/Api/ApiReleves.asmx/ChargerListeReleves', SubscriptionPage)
    download = URL(r'/Default.aspx\?dashboard=ComptesReleves&lien=SuiviReleves', DownloadDocumentPage)

    LINEBOURSE_BROWSER = LinebourseAPIBrowser
    MARKET_URL = 'https://www.caisse-epargne.offrebourse.com'

    def __init__(self, *args, **kwargs):
        # This value is useful to display deferred transactions if PSU has no card but only CHECKING account
        self.has_cards_displayed = False
        self.accounts = None
        super(CenetBrowser, self).__init__(*args, **kwargs)

        dirname = self.responses_dirname
        if dirname:
            dirname += '/bourse'

        self.linebourse = self.LINEBOURSE_BROWSER(
            self.MARKET_URL,
            logger=self.logger,
            responses_dirname=dirname,
            proxy=self.PROXIES,
        )

    def deinit(self):
        super(CenetBrowser, self).deinit()
        self.linebourse.deinit()

    def set_base_url(self):
        self.BASEURL = self.CENET_URL

    def locate_browser(self, state):
        # parent's behavior
        if self.should_skip_locate_browser():
            return

        # otherwise, force going on home to avoid some bugs on other URL GET requests.
        try:
            self.cenet_home.go()
        except (HTTPError, TooManyRedirects):
            pass

    def do_login(self):
        self.browser_switched = True
        # We use CaisseEpargneLogin do_login
        # browser_switched avoids to switch again
        super().do_login()

        # when we use CaisseEpargneLogin do_login we should reset the
        # value of BASEURL to CENET_URL (changed in login_finalize()-CaisseEpargneLogin).
        self.set_base_url()
        return

    @need_login
    def go_linebourse(self):
        data = {
            'contexte': '',
            'dateEntree': None,
            'donneesEntree': 'null',
            'filtreEntree': None,
        }
        try:
            self.linebourse_token.go(json=data)
        except BrowserUnavailable:
            # The linebourse space is not available on every connection
            raise AssertionError('No linebourse space')
        linebourse_token = self.page.get_token()

        self.location(
            self.absurl('/ReroutageSJR', self.MARKET_URL),
            data={'SJRToken': linebourse_token},
        )
        self.linebourse.session.cookies.update(self.session.cookies)
        domain = urlparse(self.url).netloc
        self.linebourse.session.headers['X-XSRF-TOKEN'] = self.session.cookies.get('XSRF-TOKEN', domain=domain)

    @need_login
    def iter_accounts(self):
        if self.accounts is None:
            data = {
                'contexte': '',
                'dateEntree': None,
                'donneesEntree': 'null',
                'filtreEntree': None,
            }

            # get accounts from CenetAccountsPage
            try:
                self.accounts = list(self.cenet_accounts.go(json=data).get_accounts())
            except ClientError:
                # Unauthorized due to wrongpass
                raise BrowserIncorrectPassword()

            # get cards, and potential missing card's parent accouts from CenetCardsPage
            try:
                self.cenet_cards.go(json=data)
            except BrowserUnavailable:
                # for some accounts, the site can throw us an error, during weeks
                self.logger.warning('ignoring cards because site is unavailable...')
            else:
                if not self.accounts:
                    shallow_parent_accounts = list(self.page.iter_shallow_parent_accounts())
                    if shallow_parent_accounts:
                        self.logger.info('Found shallow parent account(s)): %s' % shallow_parent_accounts)
                    self.accounts.extend(shallow_parent_accounts)

                cards = list(self.page.iter_cards())
                if cards:
                    self.has_cards_displayed = True
                redacted_ids = Counter(card.id[:4] + card.id[-6:] for card in cards)
                for redacted_id in redacted_ids:
                    assert redacted_ids[redacted_id] == 1, 'there are several cards with the same id %r' % redacted_id

                for card in cards:
                    card.parent = find_object(self.accounts, id=card._parent_id)
                    assert card.parent, 'no parent account found for card %s' % card
                self.accounts.extend(cards)

            # get loans from CenetLoanPage
            self.cenet_loans.go(json=data)
            for account in self.page.get_accounts():
                self.accounts.append(account)

            # get market accounts from market_accounts page
            self.cenet_market_accounts.go(json=data)
            market_accounts = list(self.page.get_accounts())
            if market_accounts:
                linebourse_account_ids = {}
                try:
                    if any(account._access_linebourse for account in market_accounts):
                        self.go_linebourse()
                        params = {'_': '{}'.format(int(time.time() * 1000))}
                        self.linebourse.account_codes.go(params=params)
                        if self.linebourse.account_codes.is_here():
                            linebourse_account_ids = self.linebourse.page.get_accounts_list()
                except AssertionError as e:
                    if str(e) != 'No linebourse space':
                        raise e
                finally:
                    self.cenet_home.go()
                for account in market_accounts:
                    for linebourse_id in linebourse_account_ids:
                        if account.id in linebourse_id:
                            account._is_linebourse = True
                    self.accounts.append(account)
        return self.accounts

    def get_loans_list(self):
        return []

    def _matches_card(self, tr, full_id):
        return fnmatch(full_id, tr.card)

    def has_no_history(self, account):
        return account.type in (account.TYPE_LOAN, account.TYPE_SAVINGS)

    @need_login
    def iter_history(self, account):
        if self.has_no_history(account):
            return []

        if getattr(account, '_is_linebourse', False):
            try:
                self.go_linebourse()
                return self.linebourse.iter_history(account.id)
            finally:
                self.cenet_home.go()

        if account.type == account.TYPE_CARD:
            if not account.parent._formated and account._hist:
                # this is a card account with a shallow parent
                return []
            else:
                # this is a card account with data available on the parent
                def match_card(tr):
                    # ex: account.number="1234123456123456", tr.card="1234******123456"
                    return fnmatch(account.number, tr.card)
                hist = self.get_history_base(account.parent, card_number=account.number)
                return keep_only_card_transactions(hist, match_card)

        if not self.has_cards_displayed:
            return self.get_history_base(account)

        # this is any other account
        return omit_deferred_transactions(self.get_history_base(account, regular_account=True))

    def get_history_base(self, account, card_number=None, regular_account=False):
        data = {
            'contexte': '',
            'dateEntree': None,
            'filtreEntree': None,
            'donneesEntree': json.dumps(account._formated),
        }
        self.cenet_account_history.go(json=data)

        while True:
            for tr in self.page.get_history(coming=False):
                # yield transactions from account

                # If the account given in this method is a card, the history we just
                # fetched from get_history() does not include card_summary detail, this will
                # have to be fetched from specific routes.
                # If the given account is a checking, this can be a regular checking account
                # or the checking account linked to a card. Depending on the case, we skip
                # or not card_summary detail, thus the regular_account check.
                if (
                    tr.type == tr.TYPE_CARD_SUMMARY and (
                        card_number or re.search(r'^CB [\d\*]+ TOT DIF .*', tr.label)
                    ) and not regular_account
                ):
                    if card_number:
                        yield tr
                        # checking if card_summary is for this card
                        assert tr.card, 'card summary has no card number?'
                        if not self._matches_card(tr, card_number):
                            continue

                    # getting detailed transactions for card_summary
                    donneesEntree = {}
                    donneesEntree['Compte'] = account._formated

                    donneesEntree['ListeOperations'] = [tr._data]
                    deferred_data = {
                        'contexte': '',
                        'dateEntree': None,
                        'donneesEntree': json.dumps(donneesEntree).replace('/', '\\/'),
                        'filtreEntree': json.dumps(tr._data).replace('/', '\\/'),
                    }
                    tr_detail_page = self.cenet_tr_detail.open(json=deferred_data)

                    parent_tr = tr
                    for tr in tr_detail_page.get_history():
                        tr.card = parent_tr.card
                        yield tr
                else:
                    # Insert yield here enables to skip card summary when PSU
                    # has no card account (cf previous explanation)
                    yield tr
            offset = self.page.next_offset()
            if not offset:
                break

            data['filtreEntree'] = json.dumps({
                'Offset': offset,
            })
            self.cenet_account_history.go(json=data)

    @need_login
    def iter_coming(self, account):
        if account.type != account.TYPE_CARD:
            return []

        trs = []

        data = {
            'contexte': '',
            'dateEntree': None,
            'donneesEntree': json.dumps(account._hist),
            'filtreEntree': None,
        }

        self.cenet_account_coming.go(json=data)
        for tr in self.page.get_history(coming=True):
            trs.append(tr)

        return sorted_transactions(trs)

    @need_login
    def iter_investments(self, account):
        if getattr(account, '_is_linebourse', False):
            try:
                self.go_linebourse()
                return self.linebourse.iter_investments(account.id)
            finally:
                self.cenet_home.go()
        return []

    @need_login
    def iter_market_orders(self, account):
        if getattr(account, '_is_linebourse', False):
            try:
                self.go_linebourse()
                return self.linebourse.iter_market_orders(account.id)
            finally:
                self.cenet_home.go()
        return []

    @need_login
    def get_advisor(self):
        return [self.cenet_home.stay_or_go().get_advisor()]

    @need_login
    def get_profile(self):
        return self.cenet_home.stay_or_go().get_profile()

    def iter_recipients(self, origin_account):
        raise NotImplementedError()

    def init_transfer(self, account, recipient, transfer):
        raise NotImplementedError()

    def new_recipient(self, recipient, **params):
        raise NotImplementedError()

    @need_login
    def iter_subscriptions(self):
        subscriber = self.get_profile().name
        json_data = {
            'contexte': '',
            'dateEntree': None,
            'donneesEntree': 'null',
            'filtreEntree': None,
        }
        self.subscription.go(json=json_data)
        return self.page.iter_subscription(subscriber=subscriber)

    @need_login
    def iter_documents(self, subscription):
        sub_id = subscription.id
        input_filter = {
            'Page': 0,
            'NombreParPage': 0,
            'Tris': [],
            'Criteres': [
                {'Champ': 'Etablissement', 'TypeCritere': 'Equals', 'Value': sub_id},
                {'Champ': 'DateDebut', 'TypeCritere': 'Equals', 'Value': None},
                {'Champ': 'DateFin', 'TypeCritere': 'Equals', 'Value': None},
                {'Champ': 'MaxRelevesAffichesParNumero', 'TypeCritere': 'Equals', 'Value': '100'},
            ],
        }
        json_data = {
            'contexte': '',
            'dateEntree': None,
            'donneesEntree': 'null',
            'filtreEntree': json.dumps(input_filter),
        }
        self.documents.go(json=json_data)
        return self.page.iter_documents(sub_id=sub_id, sub_label=subscription.label, username=self.username)

    @need_login
    def download_document(self, document):
        self.download.go()
        return self.page.download_form(document).content

    def iter_emitters(self):
        raise NotImplementedError()
