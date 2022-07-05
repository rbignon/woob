# -*- coding: utf-8 -*-

# Copyright(C) 2010-2013  Romain Bignon, Pierre Mazière
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

from decimal import Decimal
from functools import wraps
import re

from woob.capabilities.bank import (
    CapBankTransferAddRecipient, AccountNotFound,
    RecipientNotFound, TransferError, Account,
)
from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.bill import (
    CapDocument, Subscription, SubscriptionNotFound,
    Document, DocumentNotFound, DocumentTypes,
)
from woob.capabilities.contact import CapContact
from woob.capabilities.profile import CapProfile
from woob.tools.backend import Module, BackendConfig
from woob.tools.capabilities.bank.transactions import sorted_transactions
from woob.tools.value import ValueBackendPassword, Value, ValueTransient
from woob.capabilities.base import (
    find_object, NotAvailable, empty, find_object_any_match,
)

from .browser import LCLBrowser, LCLProBrowser
from .enterprise.browser import LCLEnterpriseBrowser, LCLEspaceProBrowser


__all__ = ['LCLModule']


def only_for_websites(*cfg):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if self.config['website'].get() not in cfg:
                raise NotImplementedError()

            return func(self, *args, **kwargs)

        return wrapper
    return decorator


def get_account_with_id_contained_in_iban(accounts_list, iban):
    """
    Finds the bank account in accounts_list whose «id» attribute
    is inside the IBAN, with necessary zero paddings
    Args:
        accounts_list (list[Account]): woob account objects retrieved from scraping the
            site
        iban (str): The IBAN we need to match

    Raises:
        AccountNotFound: when no account was found

    Returns:
        Account: The account whose ID matches the french IBAN part of the searched IBAN
    """
    for account in accounts_list:
        if is_account_id_in_iban(account.id, iban):
            return account
    raise AccountNotFound()


def is_account_id_in_iban(account_id, iban):
    """
    Returns True if the given account id is found inside the given IBAN, with necessary
    zero paddings.
    """
    if account_id and len(account_id) >= 5:
        # in the IBAN, the bank account number first 5 numbers is the «code guichet»
        # then the rest is padded with zeros on the left until we have 11 characters
        iban_part_with_bank_account_number = account_id[:5] + account_id[5:].zfill(11)
        return iban_part_with_bank_account_number in iban
    return False


class LCLModule(Module, CapBankWealth, CapBankTransferAddRecipient, CapContact, CapProfile, CapDocument):
    NAME = 'lcl'
    MAINTAINER = u'Romain Bignon'
    EMAIL = 'romain@weboob.org'
    VERSION = '3.1'
    DESCRIPTION = u'LCL'
    LICENSE = 'LGPLv3+'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', masked=False),
        ValueBackendPassword('password', label='Code personnel'),
        Value(
            'website',
            label='Type de compte',
            default='par',
            choices={
                'par': 'Particuliers',
                'pro': 'Professionnels',
                'ent': 'Entreprises',
                'esp': 'Espace Pro',
            },
            aliases={'elcl': 'par'}
        ),
        ValueTransient('resume'),
        ValueTransient('request_information'),
        ValueTransient('code', regexp=r'^\d{6}$'),
    )
    BROWSER = LCLBrowser

    accepted_document_types = (DocumentTypes.STATEMENT, DocumentTypes.NOTICE, DocumentTypes.REPORT, DocumentTypes.OTHER)

    def create_default_browser(self):
        # assume all `website` option choices are defined here
        browsers = {
            'par': LCLBrowser,
            'pro': LCLProBrowser,
            'ent': LCLEnterpriseBrowser,
            'esp': LCLEspaceProBrowser,
        }

        website_value = self.config['website']
        self.BROWSER = browsers.get(
            website_value.get(),
            browsers[website_value.default]
        )

        return self.create_browser(
            self.config,
            self.config['login'].get(),
            self.config['password'].get()
        )

    def iter_accounts(self):
        return self.browser.get_accounts_list()

    def get_account(self, _id):
        return find_object(self.browser.get_accounts_list(), id=_id, error=AccountNotFound)

    def iter_coming(self, account):
        return self.browser.get_coming(account)

    def iter_history(self, account):
        transactions = sorted_transactions(self.browser.get_history(account))
        return transactions

    def iter_investment(self, account):
        return self.browser.get_investment(account)

    def iter_market_orders(self, account):
        return self.browser.iter_market_orders(account)

    @only_for_websites('par', 'pro', 'elcl')
    def iter_transfer_recipients(self, origin_account):
        account = None
        if origin_account.id or origin_account.iban:
            account = self.find_account_for_transfer(
                self.iter_accounts(),
                account_id=origin_account.id,
                account_iban=origin_account.iban,
                error=None,
            )

        if not account:
            # For card accounts that do not have an iban, we make an exception because they would
            # not have recipients anyway
            if not origin_account.iban:
                return []
            # If the account has an iban this error should not happen
            raise AccountNotFound()

        return self.browser.iter_recipients(account)

    @only_for_websites('par', 'pro', 'elcl')
    def new_recipient(self, recipient, **params):
        # Recipient label has max 15 alphanumrical chars.
        recipient.label = ' '.join(w for w in re.sub('[^0-9a-zA-Z ]+', '', recipient.label).split())[:15].strip()
        return self.browser.new_recipient(recipient, **params)

    @only_for_websites('par', 'pro', 'elcl')
    def init_transfer(self, transfer, **params):
        # There is a check on the website, transfer can't be done with too long reason.
        if transfer.label:
            transfer.label = transfer.label[:30]

        self.logger.info('Going to do a new transfer')

        account = self.find_account_for_transfer(
            self.iter_accounts(),
            transfer.account_id,
            transfer.account_iban,
        )
        recipient = find_object_any_match(
            self.browser.iter_recipients(account),
            (('id', transfer.account_id), ('iban', transfer.account_iban)),
            error=RecipientNotFound,
        )

        try:
            # quantize to show 2 decimals.
            amount = Decimal(transfer.amount).quantize(Decimal(10) ** -2)
        except (AssertionError, ValueError):
            raise TransferError('something went wrong')

        return self.browser.init_transfer(account, recipient, amount, transfer.label, transfer.exec_date)

    def execute_transfer(self, transfer, **params):
        return self.browser.execute_transfer(transfer)

    def find_account_for_transfer(self, accounts, account_id=None, account_iban=None, error=AccountNotFound):
        if not (account_id or account_iban):
            raise ValueError('You must at least provide an account ID or IBAN')

        for other_account in accounts:
            # some accounts will not necessarily have an IBAN, we scrape it on the RIB page
            # but not all accounts show up
            if (
                (account_iban and other_account.iban == account_iban)
                or (account_id and other_account.id == account_id)
                # If we couldn't find a full match on the account ID or IBAN, we use a fallback strategy
                # where the account ID can be found as a substring of the IBAN
                or is_account_id_in_iban(other_account.id, account_iban)
            ):
                return other_account

        if error:
            raise error()

    def transfer_check_label(self, old, new):
        old = re.sub(r"[\(\)/<\?='!\+:#&%]", '', old).strip()
        old = old.encode('ISO8859-15', errors='replace').decode('ISO8859-15')  # latin-15
        # if no reason given, the site changes the label
        if not old and ("INTERNET-FAVEUR" in new):
            return True
        return super(LCLModule, self).transfer_check_label(old, new)

    def transfer_check_account_iban(self, old, new):
        # Some accounts' ibans cannot be found anymore on the website. But since we
        # kept the iban stored on our side, the 'old' transfer.account_iban is not
        # empty when making a transfer. When we do not find the account based on its iban,
        # we search it based on its id. So the account is valid, the iban is just empty.
        # This check allows to not have an assertion error when making a transfer from
        # an account in this situation.
        if empty(new):
            return True
        return old == new

    def transfer_check_recipient_iban(self, old, new):
        # Some recipients' ibans cannot be found anymore on the website. But since we
        # kept the iban stored on our side, the 'old' transfer.recipient_iban is not
        # empty when making a transfer. When we do not find the recipient based on its iban,
        # we search it based on its id. So the recipient is valid, the iban is just empty.
        # This check allows to not have an assertion error when making a transfer from
        # an recipient in this situation.
        # For example, this case can be encountered for internal accounts
        if empty(new):
            return True
        return old == new

    def transfer_check_account_id(self, old, new):
        # We can't verify here automatically that the account_id has not changed
        # as it might have changed early if a stet account id was provided instead
        # of the account id that we use here coming from the website.
        # The test "account_id not changed" will be performed directly inside init_transfer
        return True

    @only_for_websites('par', 'elcl', 'pro')
    def iter_contacts(self):
        return self.browser.get_advisor()

    def get_profile(self):
        if not hasattr(self.browser, 'get_profile'):
            raise NotImplementedError()

        profile = self.browser.get_profile()
        if profile:
            return profile
        raise NotImplementedError()

    @only_for_websites('par', 'elcl', 'pro')
    def get_document(self, _id):
        return find_object(self.iter_documents(None), id=_id, error=DocumentNotFound)

    @only_for_websites('par', 'elcl', 'pro')
    def get_subscription(self, _id):
        return find_object(self.iter_subscription(), id=_id, error=SubscriptionNotFound)

    @only_for_websites('par', 'elcl', 'pro')
    def iter_bills(self, subscription):
        return self.iter_documents(None)

    @only_for_websites('par', 'elcl', 'pro')
    def iter_documents(self, subscription):
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)

        return self.browser.iter_documents(subscription)

    @only_for_websites('par', 'elcl', 'pro')
    def iter_subscription(self):
        return self.browser.iter_subscriptions()

    @only_for_websites('par', 'elcl', 'pro')
    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)
        if document.url is NotAvailable:
            return

        return self.browser.open(document.url).content

    def iter_resources(self, objs, split_path):
        if Account in objs:
            self._restrict_level(split_path)
            return self.iter_accounts()
        if Subscription in objs:
            self._restrict_level(split_path)
            return self.iter_subscription()
