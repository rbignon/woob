# Copyright(C) 2022-2023 Powens
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

from datetime import date
from time import time

from woob.browser.browsers import LoginBrowser, StatesMixin, need_login
from woob.browser.url import URL
from woob.exceptions import AuthMethodNotImplemented, BrowserIncorrectPassword

from .pages import (
    CheckingAccountsPage,
    HistoryDetailPage,
    HistoryPage,
    HistorySearchPage,
    HomePage,
    LoginAjaxPage,
    LoginPage,
)


class MaFrenchBankBrowser(LoginBrowser, StatesMixin):
    BASEURL = "https://mescomptes.mafrenchbank.fr/"

    home = URL(r"fr$", HomePage)
    login = URL(r"fr/Login$", LoginPage)

    login_ajax = URL(r"fr/LoginMain/Account/JsonLogin", LoginAjaxPage)

    accounts = URL(r"fr/Accounts/Accounts/List", CheckingAccountsPage)
    history_search = URL(r"fr/Pfm/TransactionHistory\?", HistorySearchPage)
    history = URL(r"fr/Pfm/TransactionHistory/TransactionList", HistoryPage)
    history_detail = URL(r"fr/Pfm/Transaction/Details\?", HistoryDetailPage)

    def __init__(self, config, *args, **kwargs):
        username = config["login"].get()
        password = config["password"].get()
        super().__init__(username, password, *args, **kwargs)

    def build_request(self, *args, **kwargs):
        request = super().build_request(*args, **kwargs)

        # Most requests are done in AJAX, using URL.open instead of URL.go,
        # which means we have a page we're located on, either `home` or
        # `login`, and pages we open asynchronously.
        #
        # If our base page is the home page, we need to get values from the
        # page that we can use in asynchronous pages.
        if self.home.is_here():
            request.headers["NonceValue"] = self.page.get_nonce()
            request.headers["X-Request-Verification-Token"] = self.page.get_verification_token()
            request.headers["X-Tab-Id"] = self.session.cookies.get("neo_tabId")

        return request

    def do_login(self):
        self.login.go()
        page = self.login_ajax.open(
            data={
                "Lang": "",
                "Password": self.password,
                "Scenario": "Default",
                "Seed": self.page.get_seed(),
                "UserName": self.username,
            }
        )

        # TODO: SCAs could not be triggered by:
        #       - Restarting the login from a new browser (forgetful Firefox).
        #       - Switching to a new IP (through a proxy).
        #       - Changing the password and doing the above.
        if page.is_sca_required():
            raise AuthMethodNotImplemented()

        error = page.get_error_message()
        is_successful = page.is_successful()
        if not is_successful or error:
            if error.casefold() == "identifiant ou mot de passe invalide":
                raise BrowserIncorrectPassword(error)

            if error:
                raise AssertionError(
                    f"Unhandled login error message: {error!r}",
                )

            raise AssertionError(
                "Login attempt marked as unsuccessful for an unknown reason.",
            )

        self.home.go()

    @need_login
    def iter_accounts(self):
        # NOTE: Cards are not fetched because no instance of deferred
        #       cards have been found yet.

        page = self.accounts.open(
            data=b"",
            # This header is required! Otherwise, the server returns a 500.
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        return page.iter_accounts()

    @need_login
    def iter_history(self, account):
        # We need to get the product identifier for the given account, out
        # of the search page.
        page = self.history_search.open(
            params={"_": int(time() * 1000)},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        product_id = page.get_product_id(account.id)

        # Now we have the product identifier, we can get the transactions
        # for it.
        today = date.today()
        period_from = date(today.year - 1, today.month, 1).strftime("%d.%m.%Y")
        period_to = today.strftime("%d.%m.%Y")

        page = self.history.open(
            json={
                "AmountFrom": None,
                "AmountTo": None,
                "CategoryId": "0",
                "ProductIds": [product_id],
                "SaveSessionProductIds": False,
                "SaveShowIrrelevantTransactions": False,
                "SaveShowSavingsAndInvestments": False,
                "ShowCreditTransactionTypes": False,
                "ShowDebitTransactionTypes": False,
                "ShowIrrelevantTransactions": True,
                "ShowSavingsAndInvestments": True,
                "ShowUncertainTransactions": False,
                "UseAbsoluteSearch": False,
                "periodFrom": period_from,
                "periodTo": period_to,
                "_dc": int(time() * 1000),
            },
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

        for tr in page.iter_history():
            page = self.history_detail.open(
                params={
                    "_": int(time() * 1000),
                    "transactionId": tr._transaction_id,
                },
                headers={"X-Requested-With": "XMLHttpRequest"},
            )

            yield page.get_transaction(obj=tr)
