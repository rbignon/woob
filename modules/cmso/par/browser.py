# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
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

import time
from datetime import date
from functools import wraps

from weboob.browser.browsers import TwoFactorBrowser, URL, need_login
from weboob.browser.exceptions import ClientError, ServerError
from weboob.exceptions import BrowserIncorrectPassword, BrowserUnavailable, BrowserQuestion
from weboob.capabilities.bank import Account, Transaction, AccountNotFound
from weboob.capabilities.base import find_object
from weboob.tools.capabilities.bank.transactions import sorted_transactions
from weboob.tools.compat import urlparse, parse_qsl
from weboob.tools.value import Value
from weboob.tools.json import json

from .pages import (
    LogoutPage, AccountsPage, HistoryPage, LifeinsurancePage, MarketPage,
    AdvisorPage, LoginPage, ProfilePage, RedirectInsurancePage,
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
            cb = lambda: func(browser, *args, **kwargs)

            for i in range(tries, 0, -1):
                try:
                    ret = cb()
                except exc_check as exc:
                    browser.headers = None
                    browser.do_login()
                    browser.logger.info('%s raised, retrying', exc)
                    continue

                if not hasattr(ret, 'next'):
                    return ret  # simple value, no need to retry on items
                return iter_retry(cb, browser, value=ret, remaining=i, exc_check=exc_check, logger=browser.logger)

            raise BrowserUnavailable('Site did not reply successfully after multiple tries')

        return wrapper
    return decorator


class CmsoParBrowser(TwoFactorBrowser):
    __states__ = ('headers',)
    STATE_DURATION = 1
    headers = None
    HAS_CREDENTIALS_ONLY = True

    BASEURL = 'https://api.cmso.com'

    login = URL(
        r'/oauth-implicit/token',
        r'/auth/checkuser',
        LoginPage
    )
    logout = URL(
        r'/securityapi/revoke',
        r'https://.*/auth/errorauthn',
        LogoutPage
    )
    accounts = URL(r'/domiapi/oauth/json/accounts/synthese(?P<type>.*)', AccountsPage)
    history = URL(r'/domiapi/oauth/json/accounts/(?P<page>.*)', HistoryPage)
    loans = URL(r'/creditapi/rest/oauth/v1/synthese', AccountsPage)
    redirect_insurance = URL(
        r'assuranceapi/v1/oauth/sso/suravenir/SYNTHESE_ASSURANCEVIE',
        r'/assuranceapi/v1/oauth/sso/suravenir/DETAIL_ASSURANCE_VIE/(?P<accid>.*)',
        RedirectInsurancePage
    )
    lifeinsurance = URL(r'https://domiweb.suravenir.fr', LifeinsurancePage)
    market = URL(r'/domiapi/oauth/json/ssoDomifronttitre',
                 r'https://www.(?P<website>.*)/domifronttitre/front/sso/domiweb/01/(?P<action>.*)Portefeuille\?csrf=',
                 r'https://www.*/domiweb/prive/particulier', MarketPage)
    advisor = URL(r'/edrapi/v(?P<version>\w+)/oauth/(?P<page>\w+)', AdvisorPage)

    transfer_info = URL(r'/domiapi/oauth/json/transfer/transferinfos', TransferInfoPage)

    # recipients
    ext_recipients_list = URL(r'/transfersfedesapi/api/beneficiaries', RecipientsListPage)
    int_recipients_list = URL(r'/transfersfedesapi/api/accounts', RecipientsListPage)
    available_int_recipients = URL(r'/transfersfedesapi/api/credited-accounts/(?P<ciphered_contract_number>.*)', AllowedRecipientsPage)

    # transfers
    init_transfer_page = URL(r'/transfersfedesapi/api/transfers/control', TransferPage)
    execute_transfer_page = URL(r'/transfersfedesapi/api/transfers', TransferPage)

    profile = URL(r'/domiapi/oauth/json/edr/infosPerson', ProfilePage)

    json_headers = {'Content-Type': 'application/json'}

    # Values needed for login which are specific for each arkea child
    name = 'cmso'
    arkea = '03'
    arkea_si = '003'
    arkea_client_id = 'RGY7rjEcGXkHe3NufA93HTUDkjnMUqrm'

    # Need for redirect_uri
    original_site = 'https://mon.cmso.com'

    def __init__(self, website, config, *args, **kwargs):
        super(CmsoParBrowser, self).__init__(config, *args, **kwargs)

        self.config = config

        self.website = website
        self.accounts_list = []
        self.logged = False

        self.AUTHENTICATION_METHODS = {
            'code': self.handle_sms,
        }

    def init_login(self):
        self.location(self.original_site)
        if self.headers:
            self.session.headers = self.headers
        else:
            self.set_profile(self.PROFILE) # reset headers but don't clear them
            self.session.cookies.clear()
            self.accounts_list = []

            data = self.get_login_data()
            self.login.go(data=data)

            if self.logout.is_here():
                raise BrowserIncorrectPassword()

            self.update_authentication_headers()

    def send_sms(self):
        contact_information = self.location('/securityapi/person/coordonnees', method='POST').json()
        data = {
            'template': '',
            'typeMedia': 'SMS',  # can be SVI for interactive voice server
            'valueMedia': contact_information['portable']['numeroCrypte']
        }
        self.location('/securityapi/otp/generate', json=data)

        raise BrowserQuestion(Value('code', label='Enter the SMS code'))

    def handle_sms(self):
        self.session.headers = self.headers
        data = self.get_sms_data()
        otp_validation = self.location('/securityapi/otp/authenticate', json=data).json()
        self.session.headers['Authorization'] = 'Bearer %s' % otp_validation['access_token']
        self.headers = self.session.headers

    def get_sms_data(self):
        return {
            'otpValue': self.code,
            'typeMedia': 'WEB',
            'userAgent': 'Mozilla/5.0 (X11; Linux x86_64; rv:68.0) Gecko/20100101 Firefox/68.0',
            'redirectUri': '%s/auth/checkuser' % self.redirect_url,
            'errorUri': '%s/auth/errorauthn' % self.redirect_url,
            'clientId': 'com.arkea.%s.siteaccessible' % self.name,
            'redirect': 'true',
            'client_id': self.arkea_client_id,
            'accessInfos': {
                'efs': self.arkea,
                'si': self.arkea_si,
            }
        }

    def get_login_data(self):
        return {
            'client_id': self.arkea_client_id,
            'responseType': 'token',
            'accessCode': self.username,
            'password': self.password,
            'clientId': 'com.arkea.%s.siteaccessible' % self.name,
            'redirectUri': '%s/auth/checkuser' % self.original_site,
            'errorUri': '%s/auth/errorauthn' % self.original_site,
            'fingerprint': 'b61a924d1245beb7469fef44db132e96',
        }

    def update_authentication_headers(self):
        hidden_params = dict(parse_qsl(urlparse(self.url).fragment))

        self.session.headers.update({
            'Authorization': "Bearer %s" % hidden_params['access_token'],
            'X-ARKEA-EFS': self.arkea,
            'X-Csrf-Token': hidden_params['access_token'],
            'X-REFERER-TOKEN': 'RWDPART',
        })
        self.headers = self.session.headers

        if hidden_params.get('scope') == 'consent':
            self.check_interactive()
            self.send_sms()

    def get_account(self, _id):
        return find_object(self.iter_accounts(), id=_id, error=AccountNotFound)

    @retry((ClientError, ServerError))
    @need_login
    def iter_accounts(self):
        if self.accounts_list:
            return self.accounts_list

        seen = {}
        seen_savings = {}
        owner_name = self.get_profile().name.upper()

        self.transfer_info.go(json={"beneficiaryType": "INTERNATIONAL"})
        numbers = self.page.get_numbers()
        # to know if account can do transfer
        accounts_eligibilite_debit = self.page.get_eligibilite_debit()

        # First get all checking accounts...
        self.accounts.go(json={'typeListeCompte': 'COMPTE_SOLDE_COMPTES_CHEQUES'}, type='comptes')
        self.page.check_response()
        for key in self.page.get_keys():
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
            for a in page.iter_savings(key=key, numbers=numbers, name=owner_name):
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

    def _go_market_history(self):
        content = self.market.go(json={'place': 'SITUATION_PORTEFEUILLE'}).text
        self.location(json.loads(content)['urlSSO'])

        return self.market.go(website=self.website, action='historique')

    @retry((ClientError, ServerError))
    @need_login
    def iter_history(self, account):
        account = self.get_account(account.id)

        if account.type in (Account.TYPE_LOAN, Account.TYPE_PEE):
            return []

        if account.type == Account.TYPE_LIFE_INSURANCE:
            if not account.url and not hasattr(account, '_index'):
                # No url and no _index, we can't get history
                return []
            url = account.url or self.redirect_insurance.go(accid=account._index).get_url()
            url = self.location(url).page.get_link("opérations")
            return self.location(url).page.iter_history()
        elif account.type in (Account.TYPE_PEA, Account.TYPE_MARKET):
            self._go_market_history()
            if not self.page.go_account(account.label, account._owner):
                return []

            if not self.page.go_account_full():
                return []

            # Display code ISIN
            self.location(self.url, params={'reload': 'oui', 'convertirCode': 'oui'})
            # don't rely on server-side to do the sorting, not only do you need several requests to do so
            # but the site just toggles the sorting, resulting in reverse order if you browse multiple accounts
            return sorted_transactions(self.page.iter_history())

        # Getting a year of history
        # We have to finish by "SIX_DERNIERES_SEMAINES" to get in priority the transactions with ids.
        # In "SIX_DERNIERES_SEMAINES" you can have duplicates transactions without ids of the previous two months.
        nbs = ["DEUX", "TROIS", "QUATRE", "CINQ", "SIX", "SEPT", "HUIT", "NEUF", "DIX", "ONZE", "DOUZE", "SIX_DERNIERES_SEMAINES"]
        trs = []

        self.history.go(json={"index": account._index}, page="pendingListOperations")

        has_deferred_cards = self.page.has_deferred_cards()

        self.history.go(
            json={
                'index': account._index,
                'filtreOperationsComptabilisees': "MOIS_MOINS_UN"
            },
            page="detailcompte"
        )
        self.trs = set()

        for tr in self.page.iter_history(index=account._index, nbs=nbs):
            # Check for duplicates
            if tr._operationid in self.trs:
                continue
            self.trs.add(tr._operationid)
            if has_deferred_cards and tr.type == Transaction.TYPE_CARD:
                tr.type = Transaction.TYPE_DEFERRED_CARD
                tr.bdate = tr.rdate

            trs.append(tr)

        return sorted_transactions(trs)

    @retry((ClientError, ServerError))
    @need_login
    def iter_coming(self, account):
        account = self.get_account(account.id)

        if account.type is Account.TYPE_LOAN:
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
                    c.type = Transaction.TYPE_DEFERRED_CARD # force deferred card type for comings inside cards

                c.vdate = None # vdate don't work for comings

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
            data = {"place": "SITUATION_PORTEFEUILLE"}
            response = self.market.go(json=data)
            self.location(json.loads(response.text)['urlSSO'])
            self.market.go(website=self.website, action="situation")
            if self.page.go_account(account.label, account._owner):
                return self.page.iter_investment()
            return []
        raise NotImplementedError()

    def iter_internal_recipients(self, account):
        self.int_recipients_list.go()
        all_int_recipients = list(self.page.iter_int_recipients())

        ciphered_contract_number = None
        all_int_rcpt_contract_numbers = []
        # Retrieves all the ciphered contract numbers
        # of all internal recipients and find the contract
        # number of the current account we want the recipients
        # of.
        for rcpt in all_int_recipients:
            if rcpt.id == account._recipient_id:
                account._type = rcpt._type
                ciphered_contract_number = rcpt._ciphered_contract_number
            all_int_rcpt_contract_numbers.append(rcpt._ciphered_contract_number)

        assert ciphered_contract_number, 'Could not make a link between internal recipients and account (due to custom label ?)'

        # Retrieve the list of ciphered contract numbers
        # the current account can make transfer too.
        self.available_int_recipients.go(
            ciphered_contract_number=ciphered_contract_number,
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
            if rcpt._ciphered_iban not in seen_ciphered_iban:
                seen_ciphered_iban.add(rcpt._ciphered_iban)
                yield rcpt

    @need_login
    def iter_recipients(self, account):
        if account.type not in (Account.TYPE_CHECKING, Account.TYPE_SAVINGS, Account.TYPE_DEPOSIT):
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
            'amount': {
                'value': amount,
                'currencyCode': account.currency,
                'paymentCurrencyCode': account.currency,
                'exchangeValue': 1,
                'paymentValue': amount,
            },
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
                nb = -1
                for nb, sent in enumerate(self.items):
                    new = next(self.it)
                    if hasattr(new, 'iter_fields'):
                        equal = dict(sent.iter_fields()) == dict(new.iter_fields())
                    else:
                        equal = sent == new
                    if not equal:
                        # safety is not guaranteed
                        raise BrowserUnavailable('Site replied inconsistently between retries, %r vs %r', sent, new)
            except StopIteration:
                raise BrowserUnavailable('Site replied fewer elements (%d) than last iteration (%d)', nb + 1, len(self.items))
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
