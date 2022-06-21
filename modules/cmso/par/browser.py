# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
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

import time
import os
import base64
from datetime import date
from decimal import Decimal
from functools import wraps
from hashlib import sha256
from urllib.parse import urlparse, parse_qsl

from woob.browser.browsers import URL, need_login
from woob.browser.mfa import TwoFactorBrowser
from woob.browser.exceptions import ClientError, ServerError
from woob.exceptions import BrowserIncorrectPassword, BrowserUnavailable, BrowserQuestion
from woob.capabilities.bank import Account, Transaction, AccountNotFound
from woob.capabilities.base import find_object, empty
from woob.tools.capabilities.bank.transactions import sorted_transactions
from woob.tools.value import Value
from woob.tools.json import json

from .pages import (
    LogoutPage, AccountsPage, HistoryPage, LifeinsurancePage, MarketPage,
    AdvisorPage, LoginPage, ProfilePage, RedirectInsurancePage, SpacesPage,
    ChangeSpacePage, AccessTokenPage, ConsentPage,
)
from .transfer_pages import TransferInfoPage, RecipientsListPage, TransferPage, AllowedRecipientsPage


def retry(exc_check, tries=4):
    """Decorate a function to retry several times in case of exception.

    The decorated function is called at max 4 times. It is retried only when it
    raises an exception of the type `exc_check`.
    If the function call succeeds and returns an iterator, a wrapper to the
    iterator is returned. If iterating on the result raises an exception of type
    `exc_check`, the iterator is recreated by re-calling the function, but the
    values already yielded will not be re-yielded.
    For consistency, the function MUST always return values in the same order.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(browser, *args, **kwargs):
            def cb():
                return func(browser, *args, **kwargs)

            for i in range(tries, 0, -1):
                try:
                    ret = cb()
                except exc_check as exc:
                    browser.headers = None
                    browser.do_login()
                    browser.logger.info('%s raised, retrying', exc)
                    continue

                if not hasattr(ret, 'next') and not hasattr(ret, '__next__'):
                    return ret  # simple value, no need to retry on items
                return iter_retry(cb, browser, value=ret, remaining=i, exc_check=exc_check, logger=browser.logger)

            raise BrowserUnavailable('Site did not reply successfully after multiple tries')

        return wrapper
    return decorator


class CmsoLoginBrowser(TwoFactorBrowser):
    __states__ = ('login_session_id', 'login_verifier', )
    STATE_DURATION = 5  # SMS validity
    headers = None
    HAS_CREDENTIALS_ONLY = True
    NEW_PROFILE = True

    BASEURL = 'https://api.cmso.com'

    login = URL(
        r'/securityapi/checkuser',
        r'/auth/checkuser',
        LoginPage
    )
    logout = URL(
        r'/securityapi/revoke',
        r'https://.*/auth/errorauthn',
        LogoutPage
    )

    json_headers = {'Content-Type': 'application/json'}

    authorization_uri = URL(r'/oauth/authorize')
    authorization_codegen_uri = URL(r'/oauth/authorization-code')
    redirect_uri = 'https://mon.cmso.com/auth/checkuser'
    error_uri = 'https://mon.cmso.com/auth/errorauthn'
    client_uri = 'com.arkea.cmso.siteaccessible'

    spaces = URL(r'/domiapi/oauth/json/accesAbonnement', SpacesPage)
    consent = URL(r'/consentapi/tpp/consents', ConsentPage)
    change_space = URL(r'/securityapi/changeSpace', ChangeSpacePage)
    access_token = URL(r'/oauth/token', AccessTokenPage)

    # Values needed for login which are specific to each Arkea child.
    name = 'cmso'
    arkea = '03'
    arkea_si = '003'
    arkea_client_id = 'RGY7rjEcGXkHe3NufA93HTUDkjnMUqrm'
    space = 'PART'

    # Need for redirect_uri
    original_site = 'https://mon.cmso.com'

    def __init__(self, config, *args, **kwargs):
        origin = kwargs.pop('origin', None)
        self.website = kwargs.pop('website', None)
        super(CmsoLoginBrowser, self).__init__(config, *args, **kwargs)

        if origin:
            self.session.headers['origin'] = origin

        self.config = config

        self.accounts_list = []
        self.login_session_id = None
        self.login_verifier = None
        self.login_challenge = None

        self.AUTHENTICATION_METHODS = {
            'code': self.handle_sms,
        }

    def code_challenge(self, verifier):
        digest = sha256(verifier.encode('utf8')).digest()
        return base64.b64encode(digest).decode('ascii')

    def code_verifier(self):
        return base64.b64encode(os.urandom(128)).decode('ascii')

    def get_pkce_codes(self):
        verifier = self.code_verifier()
        return verifier, self.code_challenge(verifier)

    def build_authorization_uri_params(self):
        return {
            'redirect_uri': self.redirect_uri,
            'client_id': self.arkea_client_id,
            'response_type': 'code',
            'error_uri': self.error_uri,
            'code_challenge_method': 'S256',
            'code_challenge': self.login_challenge,
        }

    def init_login(self):
        self.location(self.original_site)
        self.login_verifier, self.login_challenge = self.get_pkce_codes()
        params = self.build_authorization_uri_params()
        response = self.authorization_uri.go(params=params)

        # get session_id in param location url
        location_params = dict(parse_qsl(urlparse(self.url).fragment))
        self.login_session_id = location_params['session_id']

        origin = self.session.headers.get('origin', None)
        self.set_profile(self.PROFILE)  # reset headers but don't clear them
        if origin:
            # keep origin if present
            self.session.headers['origin'] = origin

        # authorization-code generation
        data = self.get_authcode_data()
        headers = self.get_tpp_headers(data)

        try:
            response = self.authorization_codegen_uri.go(
                data=data,
                params={'session_id': self.login_session_id},
                headers=headers
            )
        except ClientError as e:
            if e.response.status_code == 403:
                response = e.response.json()

                if response.get('error_code') == 'SCA_REQUIRED':
                    label = 'Saisissez le code reçu par SMS'
                    phone = response['sca_medias'][0].get('numero_masque')
                    if phone:
                        label += ' envoyé au %s' % phone
                    raise BrowserQuestion(Value('code', label=label))
            raise

        location_params = dict(parse_qsl(urlparse(response.headers['Location']).fragment))

        if location_params.get('error'):
            if location_params.get('error_description') == 'authentication-failed':
                raise BrowserIncorrectPassword()
            # we encounter this case when an error comes from the website
            elif location_params['error'] == 'server_error':
                raise BrowserUnavailable()

        # authentication token generation
        data = self.get_tokengen_data(location_params['code'])
        self.access_token.go(json=data)
        self.update_authentication_headers()

        self.login.go(json={'espaceApplication': self.space})
        self.setup_space_after_login()

    def handle_sms(self):
        data = {
            'access_code': self.username,
            'password': self.code,
            'authenticationMethod': 'SMS_MFA2',
        }
        headers = self.get_tpp_headers(data)
        self.authorization_codegen_uri.go(
            params={'session_id': self.login_session_id},
            data=data,
            headers=headers
        )
        location_params = dict(parse_qsl(urlparse(self.response.headers['Location']).fragment))

        if location_params.get('error'):
            if location_params.get('error_description') == 'authentication-failed':
                raise BrowserIncorrectPassword()
            # we encounter this case when an error comes from the website
            elif location_params['error'] == 'server_error':
                raise BrowserUnavailable()

        data = {
            'code': location_params['code'],
            'grant_type': 'authorization_code',
            'client_id': self.arkea_client_id,
            'redirect_uri': self.redirect_uri,
            'code_verifier': self.login_verifier,
        }

        self.access_token.go(json=data)
        self.update_authentication_headers()
        self.login.go(json={'espaceApplication': self.space})
        self.setup_space_after_login()

    def setup_space_after_login(self):
        self.spaces.go(json={'includePart': True})
        part_space = self.page.get_part_space()
        if part_space is None:
            # If there is no PAR space, then the PAR browser returns no account.
            # Also, if part_space is None, `self.change_space.go()` will crash
            # because `Object numContractDestination must not be null`
            # So we just finish the login and return
            self.accounts_list = None
            return
        self.change_space.go(json={
            'clientIdSource': self.arkea_client_id,
            'espaceDestination': self.space,
            'fromMobile': False,
            'numContractDestination': part_space,
        })
        self.update_authentication_headers()

    def get_authcode_data(self):
        return {
            'access_code': self.username,
            'password': self.password,
            'space': self.space,
        }

    def get_tokengen_data(self, code):
        return {
            'client_id': self.arkea_client_id,
            'code': code,
            'grant_type': 'authorization_code',
            'code_verifier': self.login_verifier,
            'redirect_uri': self.redirect_uri,
        }

    def get_tpp_headers(self, data=''):
        # This method can be overload by a TPP
        # to add specific headers and be recognize by the bank
        return {}

    def update_authentication_headers(self):
        token = self.page.get_access_token()
        self.session.headers['Authorization'] = "Bearer %s" % token
        self.session.headers['X-ARKEA-EFS'] = self.arkea
        self.session.headers['X-Csrf-Token'] = token
        self.session.headers['X-REFERER-TOKEN'] = 'RWDPART'


class CmsoParBrowser(CmsoLoginBrowser):
    accounts = URL(r'/domiapi/oauth/json/accounts/synthese(?P<type>.*)', AccountsPage)
    history = URL(r'/domiapi/oauth/json/accounts/(?P<page>.*)', HistoryPage)
    loans = URL(r'/creditapi/rest/oauth/v1/synthese', AccountsPage)
    redirect_insurance = URL(
        r'assuranceapi/v1/oauth/sso/suravenir/SYNTHESE_ASSURANCEVIE',
        r'/assuranceapi/v1/oauth/sso/suravenir/DETAIL_ASSURANCE_VIE/(?P<accid>.*)',
        RedirectInsurancePage
    )
    lifeinsurance = URL(r'https://domiweb.suravenir.fr', LifeinsurancePage)
    market = URL(
        r'/domiapi/oauth/json/ssoDomifronttitre',
        r'https://www.(?P<website>.*)/domifronttitre/front/sso/domiweb/01/(?P<action>.*)\?csrf=',
        r'https://www.*/domiweb/prive/particulier',
        MarketPage
    )
    advisor = URL(r'/edrapi/v(?P<version>\w+)/oauth/(?P<page>\w+)', AdvisorPage)

    transfer_info = URL(r'/domiapi/oauth/json/transfer/transferinfos', TransferInfoPage)

    # recipients
    ext_recipients_list = URL(r'/transfersfedesapi/api/beneficiaries', RecipientsListPage)
    int_recipients_list = URL(r'/transfersfedesapi/api/accounts', RecipientsListPage)
    available_int_recipients = URL(
        r'/transfersfedesapi/api/credited-accounts/(?P<ciphered_contract_number>.*)',
        AllowedRecipientsPage
    )

    # transfers
    init_transfer_page = URL(r'/transfersfedesapi/api/transfers/control', TransferPage)
    execute_transfer_page = URL(r'/transfersfedesapi/api/transfers', TransferPage)

    profile = URL(r'/personapi/api/v2/clients/me/infos', ProfilePage)

    def get_account(self, _id):
        return find_object(self.iter_accounts(), id=_id, error=AccountNotFound)

    @retry((ClientError, ServerError))
    @need_login
    def iter_accounts(self):
        if self.accounts_list is None:
            # No PAR space available
            return []
        elif self.accounts_list:
            return self.accounts_list

        seen = {}
        seen_savings = {}
        livret_ibans = {}
        owner_name = self.get_profile().name.upper()

        self.transfer_info.go(json={"beneficiaryType": "INTERNATIONAL"})
        numbers = self.page.get_numbers()
        # to know if account can do transfer
        accounts_eligibilite_debit = self.page.get_eligibilite_debit()

        # First get all checking accounts...
        # We might have some savings accounts here for special cases such as mandated accounts
        # (e.g children's accounts)
        self.accounts.go(json={'typeListeCompte': 'COMPTE_SOLDE_COMPTES_CHEQUES'}, type='comptes')
        self.page.check_response()
        for key in self.page.get_keys():
            livret_ibans.update(self.page.get_livret_ibans(key))
            for a in self.page.iter_accounts(key=key):
                a._eligible_debit = accounts_eligibilite_debit.get(a.id, False)
                # Can have duplicate account, avoid them
                if a._index not in seen:
                    self.accounts_list.append(a)
                    seen[a._index] = a

        # Next, get saving accounts
        numbers.update(self.page.get_numbers())
        page = self.accounts.go(json={}, type='epargne')
        for key in page.get_keys():
            for a in page.iter_savings(key=key, numbers=numbers, name=owner_name, livret_ibans=livret_ibans):
                seen_savings[a.id] = a
                a._eligible_debit = accounts_eligibilite_debit.get(a.id, False)
                if a._index in seen:
                    acc = seen[a._index]
                    self.accounts_list.remove(acc)
                    self.logger.warning('replace %s because it seems to be a duplicate of %s', seen[a._index], a)
                self.accounts_list.append(a)

        # Some saving accounts are not on the same page
        # In this case we have no _index, we have the details url directly
        url = self.redirect_insurance.go().get_url()
        self.location(url)
        for a in self.page.iter_accounts():
            # Accounts can be on both pages. Info are slightly out-of-sync on both sites (balances are different).
            # We keep this one because it's more coherent with invests data.
            if a.id in seen_savings:
                acc = seen_savings[a.id]
                # We keep the _index because it's not available on the other website
                a._index = acc._index
                self.accounts_list.remove(acc)
                self.logger.warning('replace %s because it seems to be a duplicate of %s', seen_savings[a.id], a)
            url = a.url or self.redirect_insurance.go(accid=a._index).get_url()
            self.location(url)
            if self.lifeinsurance.is_here():
                self.page.fill_account(obj=a)
            self.accounts_list.append(a)

        # Then, get loans
        for key in self.loans.go().get_keys():
            for a in self.page.iter_loans(key=key):
                if a.id in seen:
                    self.logger.warning('skipping %s because it seems to be a duplicate of %s', seen[a.id], a)

                    account_found = False
                    for account in list(self.accounts_list):
                        # Loan id can be not unique when it also appears in json account page
                        if a.id == account._index:
                            account_found = True
                            # Merge information from account to loan
                            a.id = account.id
                            a.currency = account.currency
                            a.coming = account.coming
                            a.total_amount = account._total_amount
                            a._index = account._index
                            self.accounts_list.remove(account)
                            break
                    assert account_found

                self.accounts_list.append(a)
        return self.accounts_list

    def _go_market_history(self, action):
        try:
            url_before_market_history = json.loads(self.market.go(json={'place': 'SITUATION_PORTEFEUILLE'}).text)['urlSSO']
        except KeyError:
            raise AssertionError('unable to get url to reach to be able to go on market page')
        self.location(url_before_market_history)
        return self.market.go(website=self.website, action=action)

    def _return_from_market(self):
        # This function must be called after going to the market space.
        # The next call fails if the referer host is not the API base url.
        self.url = self.BASEURL

    @retry((ClientError, ServerError))
    @need_login
    def iter_history(self, account):
        account = self.get_account(account.id)

        if account.type in (Account.TYPE_LOAN, Account.TYPE_PEE):
            return

        if account.type == Account.TYPE_LIFE_INSURANCE:
            if not account.url and not hasattr(account, '_index'):
                # No url and no _index, we can't get history
                return
            url = account.url or self.redirect_insurance.go(accid=account._index).get_url()
            url = self.location(url).page.get_link("opérations")
            self.location(url)
            for tr in self.page.iter_history():
                yield tr
            return
        elif account.type in (Account.TYPE_PEA, Account.TYPE_MARKET):
            try:
                self._go_market_history('historiquePortefeuille')
                if not self.page.go_account(account):
                    return

                if not self.page.go_account_full():
                    return

                # Display code ISIN
                transactions_url = self.url
                self.location(transactions_url, params={'reload': 'oui', 'convertirCode': 'oui'})
                # don't rely on server-side to do the sorting, not only do you need several requests to do so
                # but the site just toggles the sorting, resulting in reverse order if you browse multiple accounts
                for tr in sorted_transactions(self.page.iter_history()):
                    if tr.amount is None:
                        self.page.go_transaction_detail(tr)
                        tr.amount = self.page.get_transaction_amount()
                        self.location(transactions_url, params={'reload': 'oui', 'convertirCode': 'oui'})
                    yield tr
                return
            finally:
                self._return_from_market()

        self.history.go(json={"index": account._index}, page="pendingListOperations")
        exception_code = self.page.get_exception_code()

        if exception_code == 300:
            # When this request returns an exception code, the request to get
            # the details will return a ServerError(500) with message "account ID not found"
            # Try a workaround of loading the account list page.
            # It seems to help the server "find" the account.
            self.accounts.go(json={'typeListeCompte': 'COMPTE_SOLDE_COMPTES_CHEQUES'}, type='comptes')

            self.history.go(json={"index": account._index}, page="pendingListOperations")
        elif exception_code is not None:
            raise AssertionError("Unknown exception_code: %s" % exception_code)

        has_deferred_cards = self.page.has_deferred_cards()

        # 1.fetch the last 6 weeks transactions but keep only the current month ones
        # those don't have any id and include 'hier' and 'Plus tôt dans la semaine'
        trs = []
        self.history.go(
            json={
                'index': account._index,
                'filtreOperationsComptabilisees': "SIX_DERNIERES_SEMAINES",
            },
            page="detailcompte"
        )
        for tr in self.page.iter_history(index=account._index, last_trs=True):
            trs.append(tr)

        # 2. get the month by month transactions
        # and avoid duplicates based on ids
        nbs = ["DEUX", "TROIS", "QUATRE", "CINQ", "SIX", "SEPT", "HUIT", "NEUF", "DIX", "ONZE", "DOUZE"]
        self.history.go(
            json={
                'index': account._index,
                'filtreOperationsComptabilisees': "MOIS_MOINS_UN",
            },
            page="detailcompte"
        )
        self.trs = set()
        for tr in self.page.iter_history(index=account._index, nbs=nbs):
            # Check for duplicates
            if tr._operationid in self.trs or (tr.id and tr.id in self.trs):
                continue
            self.trs.add(tr._operationid)
            if tr.id:
                self.trs.add(tr.id)

            if has_deferred_cards and tr.type == Transaction.TYPE_CARD:
                tr.type = Transaction.TYPE_DEFERRED_CARD
                tr.bdate = tr.rdate

            trs.append(tr)

        for tr in sorted_transactions(trs):
            yield tr

    @retry((ClientError, ServerError))
    @need_login
    def iter_coming(self, account):
        account = self.get_account(account.id)

        if account.type in (Account.TYPE_LOAN, Account.TYPE_LIFE_INSURANCE):
            return []

        comings = []
        if not hasattr(account, '_index'):
            # No _index, we can't get coming
            return []
        self.history.go(json={"index": account._index}, page="pendingListOperations")
        # There is no ids for comings, so no check for duplicates
        for key in self.page.get_keys():
            for c in self.page.iter_history(key=key):
                if hasattr(c, '_deferred_date'):
                    c.bdate = c.rdate
                    c.date = c._deferred_date
                    c.type = Transaction.TYPE_DEFERRED_CARD  # force deferred card type for comings inside cards

                c.vdate = None  # vdate don't work for comings

                comings.append(c)
        return iter(comings)

    @retry((ClientError, ServerError))
    @need_login
    def iter_investment(self, account):
        account = self.get_account(account.id)

        if account.type in (Account.TYPE_LIFE_INSURANCE, Account.TYPE_PERP):
            if not account.url and not hasattr(account, '_index'):
                # No url and no _index, we can't get investments
                return []
            url = account.url or self.redirect_insurance.go(accid=account._index).get_url()
            url = self.location(url).page.get_link("supports")
            if not url:
                return []
            return self.location(url).page.iter_investment()
        elif account.type in (Account.TYPE_MARKET, Account.TYPE_PEA):
            try:
                self._go_market_history('situationPortefeuille')
                if self.page.go_account(account):
                    return self.page.iter_investment()
                return []
            finally:
                self._return_from_market()
        raise NotImplementedError()

    @retry((ClientError, ServerError))
    @need_login
    def iter_market_orders(self, account):
        if account.type not in (Account.TYPE_MARKET, Account.TYPE_PEA):
            return

        try:
            self._go_market_history('carnetOrdre')
            if self.page.go_account(account):
                orders_list_url = self.url
                error_message = self.page.get_error_message()
                if error_message:
                    if 'AUCUN ORDRE' in error_message:
                        return
                    raise AssertionError('Unexpected error while fetching market orders')
                for order in self.page.iter_market_orders():
                    self.page.go_order_detail(order)
                    self.page.fill_market_order(obj=order)
                    self.location(orders_list_url)
                    yield order
        finally:
            self._return_from_market()

    def get_and_update_emitter_account(self, account):
        # Add the `_type` and `_ciphered_contract_number` of the account
        # if a match is made with an emitter.
        self.int_recipients_list.go()

        emitter = find_object(self.page.iter_int_recipients(availableFor='Debit'), id=account._recipient_id)
        if emitter:
            account._type = emitter._type
            account._ciphered_contract_number = emitter._ciphered_contract_number
        return emitter

    def iter_internal_recipients(self, account):
        self.int_recipients_list.go()
        all_int_recipients = list(self.page.iter_int_recipients(availableFor='Credit'))

        # Retrieves all the ciphered contract numbers of all internal recipients.
        all_int_rcpt_contract_numbers = [rcpt._ciphered_contract_number for rcpt in all_int_recipients]

        # Retrieve the list of ciphered contract numbers the account can make transfer too.
        self.available_int_recipients.go(
            ciphered_contract_number=account._ciphered_contract_number,
            json=all_int_rcpt_contract_numbers,
            headers={'Accept': 'application/json, text/plain, */*'},
        )
        allowed_rcpt_contract_numbers = json.loads(self.page.get_allowed_contract_numbers())

        for rcpt in all_int_recipients:
            if rcpt._ciphered_contract_number in allowed_rcpt_contract_numbers:
                yield rcpt

    def iter_external_recipients(self, account):
        self.ext_recipients_list.go()
        seen_ciphered_iban = set()
        for rcpt in self.page.iter_ext_recipients():
            # cmb and cmso allows the user to add multiple times the same iban...
            if rcpt._ciphered_iban not in seen_ciphered_iban:
                seen_ciphered_iban.add(rcpt._ciphered_iban)
                yield rcpt

    @need_login
    def iter_recipients(self, account):
        if account.type not in (Account.TYPE_CHECKING, Account.TYPE_SAVINGS, Account.TYPE_DEPOSIT):
            return

        if not hasattr(account, '_recipient_id') or empty(account._recipient_id):
            # Account does not have an iban so we cant match it with any emitter
            # because there might be duplicates.
            return

        account = self.get_and_update_emitter_account(account)

        # If there is no account returned, that means we were not able to find
        # the emitter matching the account. So we can't list the recipients available
        # for this account or make transfer on it.
        if not account:
            self.logger.info('Either account cannot make transfers or the link between emitters and the account could not be made.')
            return

        # Internal recipients
        for rcpt in self.iter_internal_recipients(account):
            yield rcpt

        # _type is found in iter_internal_recipients
        # and is more accurate than checking the
        # account.type since we could not be up to
        # date on the account types we handle.
        if account._type == 'SAVING':
            # Can only do transfer from savings accounts
            # to internal checking accounts.
            return

        for rcpt in self.iter_external_recipients(account):
            yield rcpt

    @need_login
    def init_transfer(self, account, recipient, amount, reason, exec_date):
        assert account.currency == 'EUR', 'Unhandled transfer to another currency'

        self.int_recipients_list.go()
        for rcpt in self.page.iter_int_recipients(availableFor='Debit'):
            if rcpt.id == account._recipient_id:
                account._ciphered_iban = rcpt._ciphered_iban
                account._ciphered_contract_number = rcpt._ciphered_contract_number
                account._bic = rcpt._bic
                break

        transfer_data = {
            'amount': self._init_transfer_amount_data(amount, account),
            'creditAccount': {
                'bic': recipient._bic,
                'cipheredBban': None,
                'cipheredIban': recipient._ciphered_iban,
                'name': recipient._owner_name,
                'currencyCode': 'EUR',
            },
            'debitAccount': {
                'currencyCode': 'EUR',
                'cipheredIban': account._ciphered_iban,
                'cipheredContractNumber': account._ciphered_contract_number,
                'bic': account._bic,
                'name': account._owner_name,
            },
            'internalTransfer': recipient.category == 'Interne',
            'periodicity': None,
            'libelleComplementaire': reason,
            'chargesType': 'SHA',
            'ignoreWarning': False,
            'debitLabel': 'de %s' % account._owner_name,
            'creditLabel': 'vers %s' % recipient._owner_name,
        }

        if recipient.category == 'Externe':
            transfer_data['creditAccount']['country'] = recipient._country

        # Found in the javascript :
        # transferTypes: {
        #    instant: 'IP',
        #    oneShotToday: 'I',
        #    recurrent: 'P',
        #    delayed: 'D'
        # },
        if exec_date and exec_date > date.today():
            transfer_data['transferType'] = 'D'
            transfer_data['executionDate'] = int(exec_date.strftime('%s')) * 1000
        else:
            transfer_data['transferType'] = 'I'
            transfer_data['executionDate'] = int(time.time() * 1000)

        self.init_transfer_page.go(json=transfer_data)
        transfer = self.page.get_transfer_with_response(account, recipient, amount, reason, exec_date)
        # transfer_data is used in execute_transfer
        transfer._transfer_data = transfer_data
        return transfer

    @staticmethod
    def _init_transfer_amount_data(amount, account):
        """
        Decimal instances should be converted to a format serializable to
        json using the built-in Python json module.

        amount.value should be a string similar to "10.00"
        amount.paymentValue should be a float
        amount.exchangeValue should be equal to amount.paymentValue
        """
        amount_string = str(amount.quantize(Decimal('0.00')))
        amount_float = float(amount)
        return {
            'value': amount_string,
            'currencyCode': account.currency,
            'paymentCurrencyCode': account.currency,
            'exchangeValue': amount_float,
            'paymentValue': amount_float,
        }

    @need_login
    def execute_transfer(self, transfer, **params):
        assert transfer._transfer_data

        self.execute_transfer_page.go(json=transfer._transfer_data)
        transfer.id = self.page.get_transfer_id()
        return transfer

    @retry((ClientError, ServerError))
    @need_login
    def get_advisor(self):
        advisor = self.advisor.go(version="2", page="conseiller").get_advisor()
        return iter([self.advisor.go(version="1", page="agence").update_agency(advisor)])

    @retry((ClientError, ServerError))
    @need_login
    def get_profile(self):
        if self.NEW_PROFILE:
            # The site changes url and method but not for all children
            # To avoid to copy retry code, NEW_PROFILE can handle it
            return self.profile.go().get_profile()
        return self.profile.go(json={}).get_profile()

    @retry((ClientError, ServerError))
    @need_login
    def iter_emitters(self):
        self.transfer_info.go(json={"beneficiaryType": "INTERNATIONAL"})
        if not self.page.check_response():
            return
        emitter_keys = ['listCompteTitulaireCotitulaire', 'listCompteMandataire', 'listCompteLegalRep']
        for key in emitter_keys:
            for em in self.page.iter_emitters(key=key):
                yield em


class iter_retry(object):
    # when the callback is retried, it will create a new iterator, but we may already yielded
    # some values, so we need to keep track of them and seek in the middle of the iterator

    def __init__(self, cb, browser, remaining=4, value=None, exc_check=Exception, logger=None):
        self.cb = cb
        self.it = value
        self.items = []
        self.remaining = remaining
        self.exc_check = exc_check
        self.logger = logger
        self.browser = browser
        self.delogged = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.remaining <= 0:
            raise BrowserUnavailable('Site did not reply successfully after multiple tries')
        if self.delogged:
            self.browser.do_login()

        self.delogged = False

        if self.it is None:
            self.it = self.cb()

            # recreated iterator, consume previous items
            try:
                for sent in self.items:
                    new = next(self.it)
                    if hasattr(new, 'iter_fields'):
                        equal = dict(sent.iter_fields()) == dict(new.iter_fields())
                    else:
                        equal = sent == new
                    if not equal:
                        # safety is not guaranteed
                        raise BrowserUnavailable('Site replied inconsistently between retries, %r vs %r', sent, new)
            except StopIteration:
                raise BrowserUnavailable('Site replied fewer elements than last iteration')
            except self.exc_check as exc:
                self.delogged = True
                if self.logger:
                    self.logger.info('%s raised, retrying', exc)
                self.it = None
                self.remaining -= 1
                return next(self)

        # return one item
        try:
            obj = next(self.it)
        except self.exc_check as exc:
            self.delogged = True
            if self.logger:
                self.logger.info('%s raised, retrying', exc)
            self.it = None
            self.remaining -= 1
            return next(self)
        else:
            self.items.append(obj)
            return obj

    next = __next__
