# -*- coding: utf-8 -*-

# Copyright(C) 2021 Damien Ramelet.
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

from __future__ import unicode_literals

from functools import wraps
from datetime import datetime, date

from woob.tools.value import Value
from woob.capabilities.bank.transfer import TransferStep
from woob.browser.exceptions import ClientError
from woob.browser.browsers import LoginBrowser, OAuth2Mixin
from woob.browser import URL

from .pages import (
    LoginPage, AccountsPage, TransactionsPage, BankDetailsPage,
    BeneficiariesPage, RefreshTokenPage, TransferPage, ConfirmTransferPage,
)


def need_login(func):
    @wraps(func)
    def inner(browser, *args, **kwargs):
        if (not hasattr(browser, 'logged') or (hasattr(browser, 'logged') and not browser.logged)) and \
                (not hasattr(browser, 'page') or browser.page is None or not browser.page.logged):
            try:
                browser.do_login()
            except ClientError as err:
                response = err.response
                # If we've tried to use an expired refresh_token
                if all([
                    "invalid_token" in response.headers.get('WWW-Authenticate', ''),
                    "expired" in response.headers.get('WWW-Authenticate', ''),
                ]):
                    browser.logger.debug("Refresh token was no longer valid. Starting login all over.")
                    browser.refresh_token = None
                    browser.access_token = None
                    browser.access_token_expire = None
                    browser.do_login()
                else:
                    raise
        return func(browser, *args, **kwargs)
    return inner


class HeliosBrowser(OAuth2Mixin, LoginBrowser):
    BASEURL = 'https://api.heliosbank.io'

    login = URL(r'/api/v1/login', LoginPage)
    accounts = URL(r'/api/v1/accounts/balance', AccountsPage)
    history = URL(r'/api/v4/accounts/transactions', TransactionsPage)  # Yep, v4
    bank_details = URL(r'/api/v1/accounts/bank_details', BankDetailsPage)
    # GET /beneficiaries return all recipients
    # POST /beneficiaries allow to add a recipient
    beneficiaries = URL(r'/api/v1/beneficiaries', BeneficiariesPage)
    transfer = URL(r'/api/v1/payments/transfer', TransferPage)
    confirm_transfer = URL(r'/api/v1/payments/transfer/(?P<transfer_id>\w{35})/confirm', ConfirmTransferPage)

    refresh = URL(r'/api/v1/refresh', RefreshTokenPage)

    token_type = 'Bearer'

    def __init__(
        self, username, password, *args, **kwargs
    ):
        super(HeliosBrowser, self).__init__(
            username, password, *args, **kwargs
        )
        self.session.headers['X-Type-Device'] = 'WEB'  # Mandatory

        self.transfer_id = None
        self.transfer_type = None

        self.__states__ += (
            'access_token_expire', 'transfer_id', 'transfer_type',
        )

    def do_login(self):
        if self.refresh_token:
            self.use_refresh_token()
            return

        self.logger.debug("Don't have any refresh token. Starting a new login.")
        self.login.go(
            json={
                'username': self.username,
                'password': self.password,
            }
        )
        self.update_token()

    def use_refresh_token(self):
        self.logger.debug("Refreshing access token.")
        self.refresh.go(json={'refreshToken': self.refresh_token})
        self.update_token()

    def update_token(self):
        self.access_token = self.page.access_token
        self.refresh_token = self.page.refresh_token
        self.access_token_expire = self.page.compute_expire()

    @need_login
    def iter_accounts(self):
        self.accounts.go()

        account = self.page.iter_accounts()

        # IBAN is provide on another page
        self.bank_details.go()
        account.iban = self.page.iban

        yield account

    @need_login
    def iter_history(self, account):
        self.history.go()
        return self.page.iter_history()

    @need_login
    def iter_recipients(self, account):
        self.beneficiaries.go()
        return self.page.iter_beneficiaries()

    @need_login
    def get_recipient(self, recipient_id):
        self.beneficiaries.go()
        return self.page.get_recipient(recipient_id=recipient_id)

    @need_login
    def new_recipient(self, recipient, **kwargs):
        return self.beneficiaries.go(json={
            'label': recipient.label,
            'iban': recipient.iban,
        })

    def has_transfer_in_progress(self, transfer, **kwargs):
        if kwargs.get('otp_sms_transfer'):
            return True

    @need_login
    def init_transfer(self, transfer, **kwargs):
        recipient = self.get_recipient(transfer.recipient_id)

        # We are providing execution date into iso format
        # without the three last micro seconds
        # Providing only date is totally fine by now
        # But avoiding potentially useless crash in the future
        if transfer.exec_date == datetime.today():
            exec_date = datetime.now().isoformat()[:-3]
        else:
            year = transfer.exec_date.year
            month = transfer.exec_date.month
            day = transfer.exec_date.day
            exec_date = date(year, month, day).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]

        self.transfer.go(json={
            'amount': transfer.amount * 100,  # Need to multiply by 100
            'description': transfer.label,
            'executeAt': exec_date,
            'recipientIban': transfer.recipient_id,
            'recipientName': recipient.label,
        })

        status = self.page.get_status()
        self.transfer_id = self.page.get_transfer_id()
        self.transfer_type = self.page.get_transfer_type()

        if status == 'CONFIRMATION_REQUIRED':
            raise TransferStep(
                transfer,
                Value(
                    'otp_sms_transfer',
                    label='Veuillez entrer le code reçu par SMS',
                ),
            )
        raise AssertionError("Unhandled status after transfer: %s" % status)

    @need_login
    def execute_transfer(self, transfer, **kwargs):
        """Execute the transfer is simply confirm it by sending the opt."""

        self.confirm_transfer.go(
            transfer_id=self.transfer_id,
            json={
                'authorizationToken': kwargs.get('otp_sms_transfer'),
                'type': self.transfer_type,
            },
        )

        # We don't want old transfer_id and transfer_type in storage
        self.transfer_id = None
        self.transfer_type = None

        return transfer
