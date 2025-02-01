# Copyright(C) 2023 Powens
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

import ssl

from woob.browser.browsers import URL, ClientError, LoginBrowser, need_login
from woob.browser.switch import SiteSwitch
from woob.exceptions import BrowserIncorrectPassword, BrowserPasswordExpired, BrowserUserBanned

from .pages import AccountsPage, HistoryPage, LoginPage, PeriodsPage


__all__ = ["LCLParcCardsBrowser"]


class LCLParcCardsBrowser(LoginBrowser):
    BASEURL = "https://cartesentreprises.secure.lcl.fr"
    TIMEOUT = 30.0

    login = URL(r"/carteaffaires/accueil", LoginPage)
    error_login = URL(r"carteaffaires/js/app.[0-9a-f]+.js", LoginPage)
    accounts = URL(r"/services/entreprise/gestionnaireparcdecartes", AccountsPage)
    periods = URL(r"/services/entreprise/gestionnairedepenses", PeriodsPage)
    historypage = URL(r"/services/porteur/operationscarteporteur", HistoryPage)

    def __init__(self, config, *args, **kwargs):
        super(LCLParcCardsBrowser, self).__init__(*args, **kwargs)
        self.entreprise_id = None

    def deinit(self):
        pass

    def prepare_request(self, req):
        preq = super(LCLParcCardsBrowser, self).prepare_request(req)

        conn = self.session.adapters["https://"].get_connection(preq.url)
        conn.ssl_version = ssl.PROTOCOL_TLSv1

        return preq

    def do_login(self):
        if not self.password.isdigit():
            raise BrowserIncorrectPassword()

        try:
            self.location("/services/users/login", json={"login": self.username, "password": self.password})
        except ClientError as e:
            if e.response.status_code == 401:
                error_type = e.response.text.replace('"', "")
                if not error_type:
                    raise BrowserIncorrectPassword()

                # Go to home page to fetch error message dynamically generated
                # by JS according to request response and error_type
                self.login.go()
                self.location(self.absurl(self.page.get_error_url()))

                if error_type == "USER_RESET_PASSWORD_ONGOING":
                    raise BrowserPasswordExpired(self.page.get_error_msg(error_type))
                if error_type == "USER_ACCOUNT_LOCKED_BY_ADMINISTRATOR":
                    raise BrowserUserBanned(self.page.get_error_msg(error_type))
                raise AssertionError(f"Unhandled error at login: {e.response.text[:100]!r}")
            raise

        self.entreprise_id = self.response.json().get("entrepriseId")
        # After log we can be redirected on the "porteur" website, or the "gestionaire" website
        if self.response.json().get("firstPageUrl") == "porteur/depensescarte":
            raise SiteSwitch("cards")
        self.session.headers["id"] = self.username

    @need_login
    def iter_accounts(self):
        json = {
            "login": None,
            "entrepriseId": self.entreprise_id,
            "groupName": None,
            "periodId": None,
            "entityId": None,
            "selectedPeriod": None,
            "entityLevel": None,
            "parentEntityId": None,
            "highEntityId": None,
            "fileToDownload": None,
            "beginIndex": 0,
            "endIndex": 20,
        }
        # We must make a request on accounts first to get the value of number of accounts
        # in order to get all accounts with only one request after that
        self.accounts.go(json=json)
        json["endIndex"] = self.page.get_end_index()
        self.accounts.go(json=json)
        return self.page.iter_accounts()

    @need_login
    def iter_history(self, account):
        json = {
            "groupName": "Gestionnaire",
            "entrepriseId": self.entreprise_id,
            "login": self.username,
        }
        self.periods.go(json=json)
        ids = self.page.get_periods()
        for _id in ids:
            json = {
                "cardId": account._card_id,
                "periodeId": _id,
                "login": self.username,
            }
            self.historypage.go(json=json)
            for tr in self.page.iter_history():
                yield tr

    @need_login
    def iter_coming(self, account):
        raise NotImplementedError()

    @need_login
    def iter_investment(self, account):
        raise NotImplementedError()
