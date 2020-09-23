# -*- coding: utf-8 -*-

# Copyright(C) 2014 Romain Bignon
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import json
import time
import operator
from datetime import date
from decimal import Decimal

from weboob.exceptions import (
    AuthMethodNotImplemented, AppValidation,
    AppValidationExpired, AppValidationCancelled,
)
from weboob.capabilities.bank import (
    Account, AddRecipientStep, AddRecipientBankError,
    TransferBankError,
)
from weboob.browser import LoginBrowser, need_login, URL, StatesMixin
from weboob.browser.exceptions import ClientError
from weboob.capabilities.base import find_object
from weboob.tools.capabilities.bank.investments import create_french_liquidity
from weboob.tools.capabilities.bank.transactions import sorted_transactions
from weboob.tools.value import Value

from .linebourse_browser import LinebourseAPIBrowser
from .pages import (
    HomePage, LoginPage, UniversePage,
    TokenPage, MoveUniversePage, SwitchPage,
    LoansPage, AccountsPage, IbanPage, LifeInsurancesPage,
    SearchPage, ProfilePage, EmailsPage, ErrorPage,
    ErrorCodePage, LinebourseLoginPage,
)
from .transfer_pages import (
    RecipientListPage, EmittersListPage, ListAuthentPage,
    InitAuthentPage, AuthentResultPage, CheckOtpPage,
    SendSmsPage, AddRecipientPage, TransferPage,
)


__all__ = ['BredBrowser']


class BredBrowser(LoginBrowser, StatesMixin):
    BASEURL = 'https://www.bred.fr'

    LINEBOURSE_BROWSER = LinebourseAPIBrowser

    home = URL(r'/$', HomePage)
    login = URL(r'/transactionnel/Authentication', LoginPage)
    error = URL(r'.*gestion-des-erreurs/erreur-pwd',
                r'.*gestion-des-erreurs/opposition',
                r'/pages-gestion-des-erreurs/erreur-technique',
                r'/pages-gestion-des-erreurs/message-tiers-oppose', ErrorPage)
    universe = URL(r'/transactionnel/services/applications/menu/getMenuUnivers', UniversePage)
    token = URL(r'/transactionnel/services/rest/User/nonce\?random=(?P<timestamp>.*)', TokenPage)
    move_universe = URL(r'/transactionnel/services/applications/listes/(?P<key>.*)/default', MoveUniversePage)
    switch = URL(r'/transactionnel/services/rest/User/switch', SwitchPage)
    loans = URL(r'/transactionnel/services/applications/prets/liste', LoansPage)
    accounts = URL(r'/transactionnel/services/rest/Account/accounts', AccountsPage)
    iban = URL(r'/transactionnel/services/rest/Account/account/(?P<number>.*)/iban', IbanPage)
    linebourse_login = URL(r'/transactionnel/v2/services/applications/SSO/linebourse', LinebourseLoginPage)
    life_insurances = URL(r'/transactionnel/services/applications/avoirsPrepar/getAvoirs', LifeInsurancesPage)
    search = URL(r'/transactionnel/services/applications/operations/getSearch/', SearchPage)
    profile = URL(r'/transactionnel/services/rest/User/user', ProfilePage)
    emails = URL(r'/transactionnel/services/applications/gestionEmail/getAdressesMails', EmailsPage)
    error_code = URL(r'/.*\?errorCode=.*', ErrorCodePage)

    list_authent = URL(r'/transactionnel/services/applications/authenticationstrong/listeAuthent/(?P<context>\w+)', ListAuthentPage)
    init_authent = URL(r'/transactionnel/services/applications/authenticationstrong/init', InitAuthentPage)
    authent_result = URL(r'/transactionnel/services/applications/authenticationstrong/result/(?P<authent_id>[^/]+)/(?P<context>\w+)', AuthentResultPage)

    check_otp = URL(r'/transactionnel/services/applications/authenticationstrong/(?P<auth_method>\w+)/check', CheckOtpPage)
    send_sms = URL(r'/transactionnel/services/applications/authenticationstrong/sms/send', SendSmsPage)

    recipient_list = URL(r'/transactionnel/v2/services/applications/virement/getComptesCrediteurs', RecipientListPage)
    emitters_list = URL(r'/transactionnel/v2/services/applications/virement/getComptesDebiteurs', EmittersListPage)

    add_recipient = URL(r'/transactionnel/v2/services/applications/beneficiaires/updateBeneficiaire', AddRecipientPage)

    create_transfer = URL(r'/transactionnel/v2/services/applications/virement/confirmVirement', TransferPage)
    validate_transfer = URL(r'/transactionnel/v2/services/applications/virement/validVirement', TransferPage)

    __states__ = (
        'auth_method', 'need_reload_state', 'authent_id',
        'context', 'new_recipient_ceiling',
    )

    def __init__(self, accnum, login, password, *args, **kwargs):
        kwargs['username'] = login
        # Bred only use first 8 char (even if the password is set to be bigger)
        # The js login form remove after 8th char. No comment.
        kwargs['password'] = password[:8]
        super(BredBrowser, self).__init__(*args, **kwargs)

        self.accnum = accnum
        self.universes = None
        self.current_univers = None

        dirname = self.responses_dirname
        if dirname:
            dirname += '/bourse'

        self.weboob = kwargs['weboob']
        self.linebourse = self.LINEBOURSE_BROWSER(
            'https://www.linebourse.fr',
            logger=self.logger,
            responses_dirname=dirname,
            weboob=self.weboob,
            proxy=self.PROXIES,
        )
        # Some accounts are detailed on linebourse. The only way to know which is to go on linebourse.
        # The parameters to do so depend on the universe.
        self.linebourse_urls = {}
        self.linebourse_tokens = {}

        self.need_reload_state = None
        self.auth_method = None
        self.authent_id = None
        self.context = None
        self.new_recipient_ceiling = None

    def load_state(self, state):
        if state.get('need_reload_state'):
            state.pop('url', None)
            super(BredBrowser, self).load_state(state)
            self.need_reload_state = None

    def do_login(self):
        if 'hsess' not in self.session.cookies:
            self.home.go()  # set session token
            assert 'hsess' in self.session.cookies, "Session token not correctly set"

        # hard-coded authentication payload
        data = dict(identifiant=self.username, password=self.password)
        self.login.go(data=data)

    @need_login
    def get_universes(self):
        """Get universes (particulier, pro, etc)"""
        self.get_and_update_bred_token()
        self.universe.go(headers={'Accept': 'application/json'})

        return self.page.get_universes()

    def get_and_update_bred_token(self):
        timestamp = int(time.time() * 1000)
        x_token_bred = self.token.go(timestamp=timestamp).get_content()
        self.session.headers.update({'X-Token-Bred': x_token_bred, })  # update headers for session
        return {'X-Token-Bred': x_token_bred, }

    def move_to_universe(self, univers):
        if univers == self.current_univers:
            return
        self.move_universe.go(key=univers)
        self.get_and_update_bred_token()
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        self.switch.go(
            data=json.dumps({'all': 'false', 'univers': univers}),
            headers=headers,
        )
        self.current_univers = univers

    @need_login
    def get_accounts_list(self):
        accounts = []
        for universe_key in self.get_universes():
            self.move_to_universe(universe_key)
            universe_accounts = []
            universe_accounts.extend(self.get_list())
            universe_accounts.extend(self.get_life_insurance_list(accounts))
            universe_accounts.extend(self.get_loans_list())
            linebourse_accounts = self.get_linebourse_accounts(universe_key)
            for account in universe_accounts:
                account._is_in_linebourse = False
                # Accound id looks like 'bred_account_id.folder_id'
                # We only want bred_account_id and we need to clean it to match it to linebourse IDs.
                account_id = account.id.strip('0').split('.')[0]
                for linebourse_account in linebourse_accounts:
                    if account_id in linebourse_account:
                        account._is_in_linebourse = True
            accounts.extend(universe_accounts)

        # Life insurances are sometimes in multiple universes, we have to remove duplicates
        unique_accounts = {account.id: account for account in accounts}
        return sorted(unique_accounts.values(), key=operator.attrgetter('_univers'))

    @need_login
    def get_linebourse_accounts(self, universe_key):
        self.move_to_universe(universe_key)
        if universe_key not in self.linebourse_urls:
            self.linebourse_login.go()
            if self.linebourse_login.is_here():
                linebourse_url = self.page.get_linebourse_url()
                if linebourse_url:
                    self.linebourse_urls[universe_key] = linebourse_url
                    self.linebourse_tokens[universe_key] = self.page.get_linebourse_token()
        if universe_key in self.linebourse_urls:
            self.linebourse.location(
                self.linebourse_urls[universe_key],
                data={'SJRToken': self.linebourse_tokens[universe_key]}
            )
            self.linebourse.session.headers['X-XSRF-TOKEN'] = self.linebourse.session.cookies.get('XSRF-TOKEN')
            params = {'_': '{}'.format(int(time.time() * 1000))}
            self.linebourse.account_codes.go(params=params)
            if self.linebourse.account_codes.is_here():
                return self.linebourse.page.get_accounts_list()
        return []

    @need_login
    def get_loans_list(self):
        self.loans.go()
        return self.page.iter_loans(current_univers=self.current_univers)

    @need_login
    def get_list(self):
        self.accounts.go()
        for acc in self.page.iter_accounts(accnum=self.accnum, current_univers=self.current_univers):
            yield acc

    @need_login
    def get_life_insurance_list(self, accounts):

        self.life_insurances.go()

        for ins in self.page.iter_lifeinsurances(univers=self.current_univers):
            ins.parent = find_object(accounts, _number=ins._parent_number, type=Account.TYPE_CHECKING)
            yield ins

    @need_login
    def _make_api_call(self, account, start_date, end_date, offset, max_length=50):
        HEADERS = {
            'Accept': "application/json",
            'Content-Type': 'application/json',
        }
        HEADERS.update(self.get_and_update_bred_token())
        call_payload = {
            "account": account._number,
            "poste": account._nature,
            "sousPoste": account._codeSousPoste or '00',
            "devise": account.currency,
            "fromDate": start_date.strftime('%Y-%m-%d'),
            "toDate": end_date.strftime('%Y-%m-%d'),
            "from": offset,
            "size": max_length,  # max length of transactions
            "search": "",
            "categorie": "",
        }
        self.search.go(data=json.dumps(call_payload), headers=HEADERS)
        return self.page.get_transaction_list()

    @need_login
    def get_history(self, account, coming=False):
        if account.type in (Account.TYPE_LOAN, Account.TYPE_LIFE_INSURANCE) or not account._consultable:
            raise NotImplementedError()

        if account._univers != self.current_univers:
            self.move_to_universe(account._univers)

        today = date.today()
        seen = set()
        offset = 0
        total_transactions = 0
        next_page = True
        end_date = date.today()
        last_date = None
        while next_page:
            if offset == 10000:
                offset = 0
                end_date = last_date
            operation_list = self._make_api_call(
                account=account,
                start_date=date(day=1, month=1, year=2000), end_date=end_date,
                offset=offset, max_length=50,
            )

            transactions = self.page.iter_history(account=account, operation_list=operation_list, seen=seen, today=today, coming=coming)

            transactions = sorted_transactions(transactions)
            if transactions:
                last_date = transactions[-1].date
            # Transactions are unsorted
            for t in transactions:
                if coming == t._coming:
                    yield t
                elif coming and not t._coming:
                    # coming transactions are at the top of history
                    self.logger.debug('stopping coming after %s', t)
                    return

            next_page = len(transactions) > 0
            offset += 50
            total_transactions += 50

            # This assert supposedly prevents infinite loops,
            # but some customers actually have a lot of transactions.
            assert total_transactions < 50000, 'the site may be doing an infinite loop'

    @need_login
    def iter_investments(self, account):
        if account.type == Account.TYPE_LIFE_INSURANCE:
            for invest in account._investments:
                yield invest

        elif account.type in (Account.TYPE_PEA, Account.TYPE_MARKET):
            if 'Portefeuille Titres' in account.label:
                if account._is_in_linebourse:
                    if account._univers != self.current_univers:
                        self.move_to_universe(account._univers)
                    self.linebourse.location(
                        self.linebourse_urls[account._univers],
                        data={'SJRToken': self.linebourse_tokens[account._univers]}
                    )
                    self.linebourse.session.headers['X-XSRF-TOKEN'] = self.linebourse.session.cookies.get('XSRF-TOKEN')
                    for investment in self.linebourse.iter_investments(account.id.strip('0').split('.')[0]):
                        yield investment
                else:
                    raise NotImplementedError()
            else:
                # Compte espèces
                yield create_french_liquidity(account.balance)

        else:
            raise NotImplementedError()

    @need_login
    def iter_market_orders(self, account):
        if account.type not in (Account.TYPE_MARKET, Account.TYPE_PEA):
            return

        if 'Portefeuille Titres' in account.label:
            if account._is_in_linebourse:
                if account._univers != self.current_univers:
                    self.move_to_universe(account._univers)
                self.linebourse.location(
                    self.linebourse_urls[account._univers],
                    data={'SJRToken': self.linebourse_tokens[account._univers]}
                )
                self.linebourse.session.headers['X-XSRF-TOKEN'] = self.linebourse.session.cookies.get('XSRF-TOKEN')
                for order in self.linebourse.iter_market_orders(account.id.strip('0').split('.')[0]):
                    yield order

    @need_login
    def get_profile(self):
        self.get_universes()

        self.profile.go()
        profile = self.page.get_profile()

        self.emails.go()
        self.page.set_email(profile=profile)

        return profile

    @need_login
    def fill_account(self, account, fields):
        if account.type == Account.TYPE_CHECKING and 'iban' in fields:
            self.iban.go(number=account._number)
            self.page.set_iban(account=account)

    @need_login
    def iter_transfer_recipients(self, account):
        self.get_and_update_bred_token()

        self.emitters_list.go(json={
            'typeVirement': 'C',
        })

        if not self.page.can_account_emit_transfer(account.id):
            return

        self.get_and_update_bred_token()
        account_id = account.id.split('.')[0]
        self.recipient_list.go(json={
            'numeroCompteDebiteur': account_id,
            'typeVirement': 'C',
        })

        for obj in self.page.iter_external_recipients():
            yield obj

        for obj in self.page.iter_internal_recipients():
            if obj.id != account.id:
                yield obj

    def handle_polling(self):
        timeout = time.time() + 300.00  # 5 minutes timeout, same as on the website
        while time.time() < timeout:
            self.get_and_update_bred_token()
            self.authent_result.go(
                authent_id=self.authent_id,
                context=self.context['contextAppli'],
            )

            status = self.page.get_status()
            if not status:
                # When the notification expires, we get a generic error message
                # instead of a status like 'PENDING'
                raise AppValidationExpired('La validation par application a expirée.')
            elif status == 'ABORTED':
                raise AppValidationCancelled("La validation par application a été annulée par l'utilisateur")
            elif status == 'AUTHORISED':
                return
            assert status == 'PENDING', "Unhandled app validation status : '%s'" % status
            time.sleep(5)
        else:
            raise AppValidationExpired('La validation par application a expirée.')

    def do_strong_authent(self, recipient):
        self.list_authent.go(context=self.context['contextAppli'])
        self.auth_method = self.page.get_handled_auth_methods()

        if not self.auth_method:
            raise AuthMethodNotImplemented()

        self.need_reload_state = self.auth_method != 'password'

        if self.auth_method == 'password':
            return self.validate_strong_authent(self.password)
        elif self.auth_method == 'otp':
            raise AddRecipientStep(
                recipient,
                Value(
                    'otp',
                    label="Veuillez générez un e-Code sur votre application BRED puis saisir cet e-Code ici",
                ),
            )
        elif self.auth_method == 'notification':
            self.init_authent.go(json={
                'context': self.context['contextAppli'],
                'type_auth': 'NOTIFICATION',
                'type_phone': 'P',
            })
            self.authent_id = self.page.get_authent_id()
            raise AppValidation(
                resource=recipient,
                message='Veuillez valider la notification sur votre application mobile BRED',
            )
        elif self.auth_method == 'sms':
            self.send_sms.go(json={
                'contextAppli': self.context['contextAppli'],
                'context': self.context['context'],
            })
            raise AddRecipientStep(
                recipient,
                Value('code', label='Veuillez saisir le code reçu par SMS'),
            )

    def validate_strong_authent(self, auth_value):
        self.get_and_update_bred_token()
        self.check_otp.go(
            auth_method=self.auth_method,
            json={
                'contextAppli': self.context['contextAppli'],
                'context': self.context['context'],
                'otp': auth_value,
            },
        )

        error = self.page.get_error()
        if error:
            raise AddRecipientBankError(message=error)

    @need_login
    def new_recipient(self, recipient, **params):
        if 'otp' in params:
            self.validate_strong_authent(params['otp'])
        elif 'code' in params:
            self.validate_strong_authent(params['code'])
        elif 'resume' in params:
            self.handle_polling()

        if not self.new_recipient_ceiling:
            if 'ceiling' not in params:
                raise AddRecipientStep(
                    recipient,
                    Value(
                        'ceiling',
                        label='Veuillez saisir le plafond maximum (tout attaché, sans points ni virgules ni espaces) de virement vers ce nouveau bénéficiaire',
                    )
                )
            self.new_recipient_ceiling = params['ceiling']

        json_data = {
            'nom': recipient.label,
            'iban': recipient.iban,
            'numCompte': '',
            'plafond': self.new_recipient_ceiling,
            'typeDemande': 'A',
        }
        try:
            self.get_and_update_bred_token()
            self.add_recipient.go(json=json_data)
        except ClientError as e:
            if e.response.status_code != 449:
                # Status code 449 means we need to do strong authentication
                raise

            self.context = e.response.json()['content']
            self.do_strong_authent(recipient)

            # Password authentication do not raise error, so we need
            # to re-execute the request here.
            if self.auth_method == 'password':
                self.get_and_update_bred_token()
                self.add_recipient.go(json=json_data)

        error = self.page.get_error()
        if error:
            raise AddRecipientBankError(message=error)

        return recipient

    @need_login
    def init_transfer(self, transfer, account, recipient, **params):
        account_id = account.id.split('.')[0]
        poste = account.id.split('.')[1]

        amount = transfer.amount.quantize(Decimal(10) ** -2)
        if not amount % 1:
            # Number is an integer without floating numbers.
            # We need to not display the floating points in the request
            # if the number is an integer or the request will not work.
            amount = int(amount)

        json_data = {
            'compteDebite': account_id,
            'posteDebite': poste,
            'deviseDebite': account.currency,
            'deviseCredite': recipient.currency,
            'dateEcheance': transfer.exec_date.strftime('%d/%m/%Y'),
            'montant': str(amount),
            'motif': transfer.label,
            'virementListe': True,
            'plafondBeneficiaire': '',
            'nomBeneficiaire': recipient.label,
            'checkBeneficiaire': False,
            'instantPayment': False,
        }

        if recipient.category == "Interne":
            recipient_id_split = recipient.id.split('.')
            json_data['compteCredite'] = recipient_id_split[0]
            json_data['posteCredite'] = recipient_id_split[1]
        else:
            json_data['iban'] = recipient.iban

        self.get_and_update_bred_token()
        self.create_transfer.go(json=json_data)

        error = self.page.get_error()
        if error:
            raise TransferBankError(message=error)

        transfer.amount = self.page.get_transfer_amount()
        transfer.currency = self.page.get_transfer_currency()

        # The same data is needed to validate the transfer.
        transfer._json_data = json_data
        return transfer

    @need_login
    def execute_transfer(self, transfer, **params):
        self.get_and_update_bred_token()
        # This sends an email to the user to tell him that a transfer
        # has been created.
        self.validate_transfer.go(json=transfer._json_data)

        error = self.page.get_error()
        if error:
            raise TransferBankError(message=error)

        return transfer
