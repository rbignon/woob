# -*- coding: utf-8 -*-

# Copyright(C) 2015      Baptiste Delpey
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

import datetime

from dateutil.relativedelta import relativedelta

from woob.exceptions import (
    ActionNeeded, AppValidationError, BrowserIncorrectPassword,
    BrowserQuestion, BrowserUnavailable, BrowserUserBanned,
)
from woob.browser import TwoFactorBrowser, URL, need_login
from woob.capabilities.bank import Account, AccountNotFound
from woob.capabilities.base import empty
from woob.tools.capabilities.bank.transactions import sorted_transactions
from woob.tools.decorators import retry
from woob.tools.capabilities.bank.investments import create_french_liquidity
from woob.tools.compat import unicode
from woob.tools.value import Value

from .pages import (
    LoginPage, ErrorPage, AccountsPage, HistoryPage, LoanHistoryPage, RibPage,
    LifeInsuranceList, LifeInsuranceIframe, LifeInsuranceRedir,
    BoursePage, CardHistoryPage, CardPage, UserValidationPage, BourseActionNeeded,
    BourseDisconnectPage, ProfilePage, BfBKeyboard, SendTwoFAPage,
)
from .spirica_browser import SpiricaBrowser


class BforbankBrowser(TwoFactorBrowser):
    BASEURL = 'https://client.bforbank.com'
    HAS_CREDENTIALS_ONLY = True
    STATE_DURATION = 5
    TWOFA_DURATION = 60 * 24 * 90

    login = URL(
        r'/connexion-client/service/login\?urlBack=%2Fespace-client',
        r'/connexion-client/service/login\?urlBack=',
        r'https://secure.bforbank.com/connexion-client/service/login\?urlBack=',
        LoginPage
    )
    user_validation = URL(
        r'/profil-client/',
        r'/connaissance-client/',
        UserValidationPage
    )
    home = URL('/espace-client/$', AccountsPage)
    rib = URL(
        '/espace-client/rib',
        r'/espace-client/rib/(?P<id>[^/]+)$',
        RibPage
    )
    loan_history = URL('/espace-client/livret/consultation.*', LoanHistoryPage)
    history = URL('/espace-client/consultation/operations/.*', HistoryPage)
    coming = URL(r'/espace-client/consultation/operationsAVenir/(?P<account>[^/]+)$', HistoryPage)
    card_history = URL('espace-client/consultation/encoursCarte/.*', CardHistoryPage)
    card_page = URL(r'/espace-client/carte/(?P<account>[^/]+)$', CardPage)

    lifeinsurance = URL(r'/espace-client/assuranceVie/(?P<account_id>\d+)')
    lifeinsurance_list = URL(r'/client/accounts/lifeInsurance/lifeInsuranceSummary.action', LifeInsuranceList)
    lifeinsurance_iframe = URL(
        r'https://(?:www|client).bforbank.com/client/accounts/lifeInsurance/consultationDetailSpirica.action',
        LifeInsuranceIframe
    )
    lifeinsurance_redir = URL(r'https://assurance-vie.bforbank.com/sylvea/welcomeSSO.xhtml', LifeInsuranceRedir)
    lifeinsurance_error = URL(
        r'/client/accounts/lifeInsurance/lifeInsuranceError.action\?errorCode=.*&errorMsg=.*',
        r'https://client.bforbank.com/client/accounts/lifeInsurance/lifeInsuranceError.action\?errorCode=.*&errorMsg=.*',
        ErrorPage
    )

    bourse_login = URL(r'/espace-client/titres/debranchementCaTitre/(?P<id>\d+)')
    bourse_action_needed = URL('https://bourse.bforbank.com/netfinca-titres/*', BourseActionNeeded)
    bourse = URL(
        'https://bourse.bforbank.com/netfinca-titres/servlet/com.netfinca.frontcr.synthesis.HomeSynthesis',
        'https://bourse.bforbank.com/netfinca-titres/servlet/com.netfinca.frontcr.account.*',
        BoursePage
    )
    # to get logout link
    bourse_titre = URL(
        r'https://bourse.bforbank.com/netfinca-titres/servlet/com.netfinca.frontcr.navigation.Titre',
        BoursePage
    )
    bourse_disco = URL(
        r'https://bourse.bforbank.com/netfinca-titres/servlet/com.netfinca.frontcr.login.Logout',
        BourseDisconnectPage
    )
    profile = URL(r'/espace-client/profil/informations', ProfilePage)
    send_twofa_page = URL(r'/connexion-client/service/resendCode/(?P<client_id>\d+)', SendTwoFAPage)

    __states__ = ('tokenDto', 'anrtoken', 'refresh_token',)

    ERROR_MAPPING = {
        'error.compte.bloque': BrowserUserBanned(
            'Suite à trois tentatives erronées, votre compte a été bloqué. Votre compte sera de nouveau disponible au bout de 24h.'
        ),
        'error.alreadySend': AppValidationError(
            'Merci de patienter 3 minutes avant de demander un nouveau code de sécurité.'
        ),
        'alreadySent': AppValidationError(
            'Merci de patienter 3 minutes avant de demander un nouveau code de sécurité.'
        ),
        'error.authentification': BrowserIncorrectPassword(
            'Les informations saisies sont incorrectes, merci de vous authentifier à nouveau. Au bout de trois tentatives erronées, votre compte sera bloqué.'
        ),
        'codeNotMatch': BrowserIncorrectPassword(
            message='Le code de sécurité saisi ne correspond pas à celui qui vous a été envoyé. Au bout de trois tentatives erronées, votre compte sera bloqué.',
            bad_fields=['code'],
        ),
        'error.technical': BrowserUnavailable(),
        'error.anrlocked': BrowserUserBanned(
            'Suite à trois tentatives erronées, vous ne pouvez plus recevoir de code par SMS pour valider les opérations sensibles. Cette fonctionnalité sera de nouveau disponible dans 24h.'
        ),
        # not a typo
        'accoundLocked': BrowserUserBanned(
            'Suite à trois tentatives erronées, vous ne pouvez plus recevoir de code par SMS pour valider les opérations sensibles. Cette fonctionnalité sera de nouveau disponible dans 24h.'
        ),
    }

    def __init__(self, config, *args, **kwargs):
        username = config['login'].get()
        password = config['password'].get()
        super(BforbankBrowser, self).__init__(config, username, password, *args, **kwargs)
        self.birthdate = self.config['birthdate'].get()
        self.accounts = None
        self.weboob = kwargs['weboob']
        self.tokenDto = None
        self.anrtoken = None
        self.refresh_token = {}

        self.spirica = SpiricaBrowser(
            'https://assurance-vie.bforbank.com/',
            *args, username=None, password=None, **kwargs
        )

        self.AUTHENTICATION_METHODS = {
            'code': self.handle_sms,
        }

    def deinit(self):
        super(BforbankBrowser, self).deinit()
        self.spirica.deinit()

    def get_expire(self):
        if self.refresh_token.get('expires'):
            return unicode(datetime.datetime.fromtimestamp(self.refresh_token['expires']))
        return super(BforbankBrowser, self).get_expire()

    def handle_errors(self, error, clear_twofa=False):
        if error and clear_twofa:
            self.clear_twofa()

        if error in self.ERROR_MAPPING:
            raise self.ERROR_MAPPING[error]
        elif error is not None:
            raise AssertionError('Unexpected error at login: "%s"' % error)

    def init_login(self):
        if not self.password.isdigit():
            raise BrowserIncorrectPassword()

        if self.refresh_token:
            self.session.cookies.set('refresh_token', self.refresh_token['value'], domain=self.refresh_token['domain'])

        self.login.stay_or_go()
        assert self.login.is_here()
        result = self.start_login()

        if result.get('eligibleForte'):  # if True, it means we're in a 2FA workflow
            self.check_interactive()

            self.tokenDto = result['tokenDto']

            # A 2FA is triggered here
            self.trigger_twofa()

            raise BrowserQuestion(
                Value(
                    'code',
                    label='Un SMS contenant un code à 4 chiffres a été communiqué sur votre téléphone portable')
            )

        # When we try to login, the server return a json, if no error occurred
        # `error` will be None otherwise it will be filled with the content of
        # the error.
        # With the exception of wrongpass errors for which the content
        # of the error is an empty string.
        error = result.get('errorMessage')
        if result.get('errorCode') == 'BindException' and not error:
            '''
            As found in '/connexion-client/js/wsso.js'

            var handleException = function (err) {
            if (err.errorCode === 'BindException') {
                handleTechnicalError("error.authentification");
            '''
            error = 'error.authentification'

        self.handle_errors(error)

        # We must go home after login otherwise do_login will be done twice.
        self.home.go()

        if self.user_validation.is_here():
            # We are sometimes redirected to a page asking to verify the client's info.
            # The page is blank before JS so the action needed message is hard-coded.
            raise ActionNeeded('Vérification de vos informations personnelles')

    def start_login(self):
        """
        Do login request without visiting the page because the page will be juste a simple JSON.
        We don't want to visit the JSON page because the 2FA will be done on the same page as the login,
        so we want to stay on it.
        """
        vk = BfBKeyboard(self.page)
        data = {}
        data['j_username'] = self.username
        data['birthDate'] = self.birthdate.strftime('%d/%m/%Y')
        data['indexes'] = vk.get_string_code(self.password)
        data['_rememberClientLogin'] = 'on'
        data['pinpadId'] = self.page.get_pinpad_id()

        result = self.open('/connexion-client/service/auth', data=data).json()

        # Renew 2FA cookies if needed
        self.handle_twofa_cookies()

        return result

    def clear_twofa(self):
        self.code = None
        self.config['code'].set(self.config['code'].default)

    def trigger_twofa(self):
        data = {}
        data['anr'] = None
        data['clientId'] = self.username
        data['tokenDto'] = self.tokenDto
        data['tokenCode'] = None

        self.send_twofa_page.go(client_id=self.username, json=data)

        if self.page.doc['error']:
            self.handle_errors(self.page.doc['messageError'])

        self.anrtoken = self.page.doc['anrtoken']
        self.tokenDto = self.page.doc['tokenDto']

    def handle_sms(self):
        data = {}
        data['anr'] = self.code
        data['clientId'] = self.username
        data['tokenDto'] = self.tokenDto
        data['tokenCode'] = self.anrtoken

        result = self.open('/connexion-client/service/authForte', json=data).json()

        error = result.get('messageError')
        self.handle_errors(error, clear_twofa=True)

        # Add/renew 2FA cookies if needed
        self.handle_twofa_cookies()

        self.home.go()

    def handle_twofa_cookies(self):
        """
        Store refresh token and its expiration date as we need to to re-login without asking a new 2FA.
        Only update refresh token if we don't have one already or we have a new one available.
        """
        for cookie in self.session.cookies:
            if (
                cookie.name == 'refresh_token' and cookie.expires
                and cookie.expires > self.refresh_token.get('expires', 0)
            ):
                self.refresh_token['value'] = cookie.value
                self.refresh_token['expires'] = cookie.expires
                self.refresh_token['domain'] = cookie.domain
                break

    @need_login
    def iter_accounts(self):
        if self.accounts is None:
            owner_name = self.get_profile().name.upper().split(' ', 1)[1]
            self.home.go()
            accounts = list(self.page.iter_accounts(name=owner_name))
            if self.page.RIB_AVAILABLE:
                # Start here, then we'll go from account's special page, for each account
                self.rib.go()
                for account in accounts:
                    # Check if rib page exists for that account before trying to reach it.
                    if self.page.has_account_listed(account):
                        self.rib.go(id=account._url_code)
                        self.page.populate_rib(account)

            self.accounts = []
            for account in accounts:
                self.accounts.append(account)

                if account.type == Account.TYPE_CHECKING:
                    self.card_page.go(account=account._url_code)
                    if self.page.has_no_card():
                        continue
                    cards = self.page.get_cards(account.id)
                    account._cards = cards
                    if cards:
                        self.location(account.url.replace('operations', 'encoursCarte') + '/0')
                        indexes = dict(self.page.get_card_indexes())

                    for card in cards:
                        # if there's a credit card (not debit), create a separate, virtual account
                        card.url = account.url
                        card.parent = account
                        card.currency = account.currency
                        card._checking_account = account
                        card._index = indexes[card.number]

                        card_url = account.url.replace('operations', 'encoursCarte')
                        card_url += '/%s' % card._index

                        self.location(card_url)
                        next_month = datetime.date.today() + relativedelta(months=1)
                        if self.page.get_debit_date().month == next_month.month:
                            card_url += '?month=1'
                            self.location(card_url)

                        card.balance = 0
                        card.coming = self.page.get_balance()
                        assert not empty(card.coming)

                        # insert it near its companion checking account
                        self.accounts.append(card)

        return iter(self.accounts)

    @need_login
    def get_history(self, account):
        if account.type == Account.TYPE_LOAN:
            return []
        elif account.type in (Account.TYPE_MARKET, Account.TYPE_PEA):
            bourse_account = self.get_bourse_account(account)
            if not bourse_account:
                return iter([])

            self.location(
                bourse_account._link_id,
                params={
                    'nump': bourse_account._market_id,
                }
            )
            assert self.bourse.is_here()
            history = list(self.page.iter_history())
            self.leave_espace_bourse()

            return history
        elif account.type == Account.TYPE_LIFE_INSURANCE:
            if not self.goto_spirica(account):
                return iter([])

            return self.spirica.iter_history(account)

        if account.type != Account.TYPE_CARD:
            self.location(account.url)
            assert self.history.is_here() or self.loan_history.is_here()
            transactions_list = []
            if account.type == Account.TYPE_CHECKING:
                # transaction of the day
                for tr in self.page.get_today_operations():
                    transactions_list.append(tr)
            # history
            for tr in self.page.get_operations():
                transactions_list.append(tr)

            return sorted_transactions(transactions_list)
        else:
            # for summary transactions, the transactions must be on both accounts:
            # negative amount on checking account, positive on card account
            transactions = []
            self.location(account.url.replace('operations', 'encoursCarte') + '/%s?month=1' % account._index)
            if self.page.get_debit_date().month == (datetime.date.today() - relativedelta(months=1)).month:
                transactions = list(self.page.get_operations())
                summary = self.page.create_summary()
                if summary:
                    transactions.insert(0, summary)
            return transactions

    @need_login
    def get_coming(self, account):
        if account.type == Account.TYPE_CHECKING:
            self.coming.go(account=account._url_code)
            return self.page.get_operations()
        elif account.type == Account.TYPE_CARD:
            self.location(account.url.replace('operations', 'encoursCarte') + '/%s' % account._index)
            transactions = list(self.page.get_operations())
            if self.page.get_debit_date().month == (datetime.date.today() + relativedelta(months=1)).month:
                self.location(account.url.replace('operations', 'encoursCarte') + '/%s?month=1' % account._index)
                transactions += list(self.page.get_operations())
            return sorted_transactions(transactions)
        else:
            raise NotImplementedError()

    def goto_lifeinsurance(self, account):
        self.lifeinsurance.go(account_id=account.id)
        self.lifeinsurance_list.go()

    @retry(AccountNotFound, tries=5)
    def goto_spirica(self, account):
        assert account.type == Account.TYPE_LIFE_INSURANCE
        self.goto_lifeinsurance(account)

        if self.login.is_here():
            self.logger.info('was logged out, relogging')
            # if we don't clear cookies, we may land on the wrong spirica page
            self.session.cookies.clear()
            self.spirica.session.cookies.clear()

            self.do_login()
            self.goto_lifeinsurance(account)

        if self.lifeinsurance_list.is_here():
            self.logger.debug('multiple life insurances, searching for %r', account)
            # multiple life insurances: dedicated page to choose
            for insurance_account in self.page.iter_accounts():
                self.logger.debug('testing %r', account)
                if insurance_account.id == account.id:
                    self.location(insurance_account.url)
                    assert self.lifeinsurance_iframe.is_here()
                    break
            else:
                raise AccountNotFound('account was not found in the dedicated page')
        else:
            assert self.lifeinsurance_iframe.is_here()

        self.location(self.page.get_iframe())
        if self.lifeinsurance_error.is_here():
            self.home.go()
            self.logger.warning('life insurance site is unavailable')
            return False

        assert self.lifeinsurance_redir.is_here()

        redir = self.page.get_redir()
        assert redir
        account.url = self.absurl(redir)
        self.spirica.session.cookies.update(self.session.cookies)
        self.spirica.logged = True
        return True

    def get_bourse_account(self, account):
        owner_name = self.get_profile().name.upper().split(' ', 1)[1]
        self.location(account.url)

        self.bourse.go()
        assert self.bourse.is_here()

        if self.page.password_required():
            return
        self.logger.debug('searching account matching %r', account)
        for bourse_account in self.page.get_list(name=owner_name):
            self.logger.debug('iterating account %r', bourse_account)
            if bourse_account.id.startswith(account.id[3:]):
                return bourse_account
        else:
            raise AccountNotFound()

    @need_login
    def iter_investment(self, account):
        if account.type == Account.TYPE_LIFE_INSURANCE:
            if not self.goto_spirica(account):
                return iter([])

            return self.spirica.iter_investment(account)
        elif account.type in (Account.TYPE_MARKET, Account.TYPE_PEA):
            bourse_account = self.get_bourse_account(account)
            if not bourse_account:
                return iter([])

            self.location(bourse_account._market_link)
            assert self.bourse.is_here()
            invs = list(self.page.iter_investment())
            # _especes is set during BoursePage accounts parsing. BoursePage
            # inherits from lcl module BoursePage
            if bourse_account._especes:
                invs.append(create_french_liquidity(bourse_account._especes))

            self.leave_espace_bourse()

            return invs

        raise NotImplementedError()

    def leave_espace_bourse(self):
        # To enter the Espace Bourse from the standard Espace Client,
        # you need to logout first from the Espace Bourse, otherwise
        # a 500 ServerError is returned.
        # Typically needed between iter_history and iter_investments when dealing
        # with a market or PEA account, or when running them twice in a row
        if self.bourse.is_here():
            self.location(self.bourse_titre.build())
            self.location(self.page.get_logout_link())
            self.login.go()

    @need_login
    def get_profile(self):
        self.profile.go()
        return self.page.get_profile()
