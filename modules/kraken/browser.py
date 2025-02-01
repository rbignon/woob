# Copyright(C) 2012-2022  Budget Insight
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

import base64
import hashlib
import hmac
import time
from datetime import datetime
from urllib.parse import urlencode

from woob.browser import URL, PagesBrowser, StatesMixin, need_login
from woob.capabilities.bank import Recipient, TransferBankError, TransferInsufficientFunds, TransferInvalidAmount
from woob.exceptions import ActionNeeded, BrowserIncorrectPassword, BrowserQuestion, NeedInteractiveFor2FA
from woob.tools.value import Value

from .pages import AssetPairsPage, AssetsPage, BalancePage, HistoryPage, TickerPage, TradePage


class KrakenBrowser(PagesBrowser, StatesMixin):
    BASEURL = "https://api.kraken.com"

    balance = URL(r"/0/private/Balance", BalancePage)
    history = URL(r"/0/private/Ledgers", HistoryPage)
    trade = URL(r"/0/private/AddOrder", TradePage)

    assets = URL(r"/0/public/Assets", AssetsPage)
    assetpairs = URL(r"/0/public/AssetPairs", AssetPairsPage)
    ticker = URL(r"/0/public/Ticker\?pair=(?P<asset_pair>.*)", TickerPage)

    __states__ = ("otp_expire", "otp")

    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config

        self.api_key = self.config["api_key"].get()
        self.private_key = self.config["private_api_key"].get()
        self.otp_enabled = self.config["otp_enabled"].get()

        self.otp_expire = None
        self.otp = None

        self.data = {}
        self.headers = {}
        self.asset_pair_list = []

        self.last_request_time = None
        self.accumulated_time = 0

    def locate_browser(self, state):
        pass

    def do_login(self):
        # Minimum availability for otp is 15 minutes, users can change that
        # settings but we can't check how much time a session last with the api.
        # So we use 15 minutes as maximum otp life.
        if self.otp_enabled and (self.otp_expire is None or (self.otp_expire and time.time() >= self.otp_expire)):
            if self.config["request_information"].get() is None:
                raise NeedInteractiveFor2FA()

            if not self.config["otp"].get():
                raise BrowserQuestion(Value("otp", label="Two factor authentication password"))

            self.otp = self.config["otp"].get()
            self.otp_expire = int(time.time() + 900)

        self.update_request_data()
        self.update_request_headers("Balance")
        self.balance.go(data=self.data, headers=self.headers)

    def sleep_for_rate_limit(self):
        current_request_time = time.time()
        last_request_time = self.last_request_time or current_request_time
        diff_time = current_request_time - last_request_time

        # A request can increment the rate limit counter by 0, 1 or 2.
        # For now, we assume that every request cost 1.
        # This could be explored further if we get rate limiting again.
        #
        # The cost of a request is of
        # - 3 sec for a basic account;
        # - 2 sec for a intermiate account;
        # - 1 sec for a pro account
        # We assume the lowest tier where it take 3 sec to offset a request.

        # At each request, we accumulate time for the new request that we will do
        # but remove the time that has passed since the last request.
        time_for_this_request = 3
        self.accumulated_time = time_for_this_request + max(self.accumulated_time - diff_time, 0)

        # In theory, we could use 45 sec (15 requests * 3 sec), but using 44 sec
        # leaves 1 sec of margin.
        wait_time = self.accumulated_time - 44

        if wait_time > 0:
            # Wait time cannot be longer than time_for_this_request.
            time.sleep(wait_time)

        self.last_request_time = current_request_time

    def open(self, *args, **kwargs):
        self.sleep_for_rate_limit()
        resp = super().open(*args, **kwargs)
        error = resp.page.get_error() or ""
        if not error:
            return resp
        if "limit exceeded" in error:
            raise AssertionError("The module is supposed to handle rate limiting correctly")
        elif "Permission denied" in error:
            # The API key lacks permissions needed to access the page
            raise ActionNeeded(
                locale="fr-FR",
                message="Merci de configurer les autorisations de votre clé API",
            )
        elif "Invalid signature" in error or "Invalid key" in error:
            raise BrowserIncorrectPassword()
        else:
            raise AssertionError('Unhandled error : "%s"' % error)

    def _sign(self, data, urlpath):
        # sign request data according to Kraken's scheme.
        postdata = urlencode(data)

        # unicode-objects must be encoded before hashing
        encoded = (str(data["nonce"]) + postdata).encode(encoding="ascii")
        message = urlpath.encode() + hashlib.sha256(encoded).digest()

        if len(self.private_key) % 4 != 0:
            # private key, has to be a base64 encoded value
            # and these kind of values are ALWAYS multiple of 4,
            # else base64.b64decode() crash
            # it may happens when user mistake private api key
            # with their website password
            raise BrowserIncorrectPassword()

        signature = hmac.new(base64.b64decode(self.private_key), message, hashlib.sha512)
        sigdigest = base64.b64encode(signature.digest())

        return sigdigest.decode(encoding="ascii")

    def update_request_headers(self, method):
        urlpath = "/0/private/" + method

        self.headers = {"API-Key": self.api_key, "API-Sign": self._sign(self.data, urlpath)}

    def update_request_data(self):
        # nonce counter: returns: an always-increasing unsigned integer (up to 64 bits wide)
        self.data["nonce"] = int(1000 * time.time())
        if self.otp:
            self.data["otp"] = self.otp

    @need_login
    def iter_accounts(self):
        self.update_request_data()
        self.update_request_headers("Balance")
        self.balance.go(data=self.data, headers=self.headers)

        return self.page.iter_accounts()

    @need_login
    def iter_history(self, account_currency):
        self.update_request_data()
        self.update_request_headers("Ledgers")
        self.history.go(data=self.data, headers=self.headers)

        return self.page.get_tradehistory(account_currency)

    @need_login
    def iter_recipients(self, account_from):
        if not self.asset_pair_list:
            self.assetpairs.go()
            self.asset_pair_list = self.page.get_asset_pairs()
        for account_to in self.iter_accounts():
            if account_to.id != account_from.id:
                asset_data = None
                # search the correct asset pair name
                for asset_pair in self.asset_pair_list:
                    if (account_from.id in asset_pair) and (account_to.id in asset_pair):
                        asset_data = asset_pair

                if asset_data:
                    recipient = Recipient()
                    recipient.label = asset_data
                    recipient.category = "Interne"
                    recipient.enabled_at = datetime.now().replace(microsecond=0)
                    recipient.id = account_from.label + "@" + account_to.label
                    yield recipient

    @need_login
    def execute_transfer(self, account, recipient, transfer):
        if recipient.label.find(account.label) > recipient.label.find(recipient.label):
            trade_type = "buy"
        else:
            trade_type = "sell"
        self.data = {
            "pair": recipient.label,
            "type": trade_type,
            "ordertype": "market",
            "volume": transfer.amount,
        }
        self.update_request_data()
        self.update_request_headers("AddOrder")
        self.trade.go(data=self.data, headers=self.headers)
        self.data = {}
        transfer_error = self.page.get_error()

        if transfer_error:
            if "EOrder" in transfer_error[0]:
                if "Insufficient funds" in transfer_error[0]:
                    raise TransferInsufficientFunds()
                raise TransferInvalidAmount(message=transfer_error[0])
            raise TransferBankError(message=transfer_error[0])
        return transfer

    @need_login
    def iter_currencies(self):
        self.assets.go()
        return self.page.iter_currencies()

    def get_rate(self, curr_from, curr_to):
        if not self.asset_pair_list:
            self.assetpairs.go()
            self.asset_pair_list = self.page.get_asset_pairs()

        # search the correct asset pair name
        for asset_pair in self.asset_pair_list:
            if (curr_from in asset_pair) and (curr_to in asset_pair):
                self.ticker.go(asset_pair=asset_pair)
                rate = self.page.get_rate()
                # in kraken API curreny_from must be the crypto in the spot price request
                if asset_pair.find(curr_from) > asset_pair.find(curr_to):
                    rate.value = 1 / rate.value
                return rate
        return
