# Copyright(C) 2022      Florian Bezannier
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

import hmac
import time
import urllib
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256

from woob.browser import APIBrowser
from woob.capabilities.bank import Account


__all__ = ["BinanceBrowser"]


class BinanceBrowser(APIBrowser):
    BASEURL = "https://api.binance.com"

    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.api_key = config["api_key"].get()
        self.secret_key = config["secret_key"].get()

    def get_snap(self, acc_type):
        ts = int(time.time() * 1000)
        yesterday = int((datetime.now() - timedelta(days=2)).timestamp() * 1000)
        data = {"timestamp": ts, "type": acc_type, "limit": 5, "startTime": yesterday}
        data_st = urllib.parse.urlencode(data, doseq=False)
        signature = hmac.new(self.secret_key.encode("utf-8"), data_st.encode("utf-8"), sha256).hexdigest()
        data_st += "&signature=" + signature
        res = self.request("/sapi/v1/accountSnapshot", params=data_st, headers={"X-MBX-APIKEY": self.api_key})
        return res

    def get_future_balance(self):
        try:
            res = self.get_snap("FUTURES")["snapshotVos"][-1]
        except KeyError:
            return 0
        assets = res["data"]["assets"]
        my_item = next((item for item in assets if item["asset"] == "USDT"), None)
        return float(my_item["walletBalance"])

    def get_ticker(self, symbol):
        res = self.request("https://www.binance.com/api/v3/ticker/price?symbol=" + symbol)
        return float(res["price"])

    def get_spot_or_margin_balance(self, acc_type):
        try:
            btc = float(self.get_snap(acc_type)["snapshotVos"][-1]["data"]["totalAssetOfBtc"])
        except KeyError:
            return 0
        btc_usd = self.get_ticker("BTCUSDT")
        return btc * btc_usd

    def get_balance(self):
        fut_balance = self.get_future_balance()
        spot_balance = self.get_spot_or_margin_balance("SPOT")
        margin_balance = self.get_spot_or_margin_balance("MARGIN")
        return fut_balance + spot_balance + margin_balance

    def get_exchange_rate_usd_to_eur(self):
        return self.get_ticker("BTCUSDT") / self.get_ticker("BTCEUR")

    def iter_accounts(self):
        usb_to_eur = self.get_exchange_rate_usd_to_eur()
        accounts_balance = {
            "Spot": self.get_spot_or_margin_balance("SPOT") / usb_to_eur,
            "Margin": self.get_spot_or_margin_balance("MARGIN") / usb_to_eur,
            "Future": self.get_future_balance(),
        }
        for acc_type, balance in accounts_balance.items():
            acc = Account()
            acc.type = Account.TYPE_MARKET
            acc.label = acc_type
            acc.id = acc_type
            acc.currency = "EUR"
            acc.balance = Decimal(balance)
            yield acc
