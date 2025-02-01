# Copyright(C) 2015 Romain Bignon
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

from woob.browser import URL, LoginBrowser, need_login
from woob.exceptions import ActionNeeded, ActionType, BrowserIncorrectPassword
from woob.tools.capabilities.bank.transactions import sorted_transactions

from .pages import AccountsPage, HistoryPage, LoginPage, LoginResultPage


__all__ = ["DelubacBrowser"]


class DelubacBrowser(LoginBrowser):
    BASEURL = "https://www.edelubac.com"

    login = URL(r"/josso/signon/entLogin.jsp", LoginPage)
    login_result = URL(r"/josso/signon/entKbvLogin.do", LoginResultPage)
    accounts = URL(r"/consultation/action/private/consultation/synthese/comptes.do", AccountsPage)
    transactions = URL(
        r"/consultation/action/private/consultation/search/index.do",
        r"consultation/action/private/consultation/search/resOperations.do",
        HistoryPage,
    )

    def do_login(self):
        self.login.go()
        self.page.login(self.username, self.password)

        if self.login_result.is_here():
            error_msg = self.page.get_error()
            error_snippets = (
                "mot de passe est incorrect",
                "your password is incorrect",
            )
            error_patterns = re.compile("|".join(error_snippets))
            if re.search(error_patterns, error_msg):
                raise BrowserIncorrectPassword(error_msg)

            sca_message = self.page.get_sca_message()
            sca_snippets = (
                "authentification forte",
                "authentication is required",
            )
            sca_patterns = re.compile("|".join(sca_snippets))
            if re.search(sca_patterns, sca_message):
                raise ActionNeeded(
                    locale="fr-FR",
                    message="Vous devez réaliser la double authentification sur le portail internet.",
                    action_type=ActionType.PERFORM_MFA,
                )
            raise AssertionError(f"Unhandled error at login: {error_msg}")

    @need_login
    def iter_accounts(self):
        self.accounts.go()
        yield from self.page.iter_accounts()

    @need_login
    def iter_history(self, account):
        self.transactions.go()
        self.page.search_transactions_form(account)
        if self.page.has_no_transaction():
            return
        yield from sorted_transactions(self.page.iter_history())
