# Copyright(C) 2012 Powens
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

from woob.browser import URL, LoginBrowser, need_login
from woob.exceptions import BrowserIncorrectPassword, BrowserUnavailable
from woob.tools.capabilities.bill.documents import merge_iterators, sorted_documents

from .pages import ConsolePage, ContractPage, DocumentsPage, HomePage, LoginPage, ProfilePage, SuiviPage


class FreeBrowser(LoginBrowser):
    BASEURL = "https://adsl.free.fr"

    login = URL(r"https://subscribe.free.fr/login/", LoginPage)
    home = URL(r"/home.pl(?P<urlid>.*)", HomePage)
    console = URL(r"https://subscribe.free.fr/accesgratuit/console/console.pl(?P<urlid>.*)", ConsolePage)
    suivi = URL(r"/suivi.pl", SuiviPage)
    documents = URL(r"/liste-factures.pl(?P<urlid>.*)", DocumentsPage)
    profile = URL(r"/modif_infoscontact.pl(?P<urlid>.*)", ProfilePage)
    address = URL(r"/show_adresse.pl(?P<urlid>.*)", ProfilePage)
    contracts = URL(r"/afficher-cgv.pl(?P<urlid>.*)", ContractPage)

    def __init__(self, private_user_agent, *args, **kwargs):
        LoginBrowser.__init__(self, *args, **kwargs)
        self.urlid = None
        self.status = "active"

        if private_user_agent:
            self.session.headers["User-Agent"] = private_user_agent

    def do_login(self):
        self.login.go()

        self.page.login(self.username, self.password)

        if self.login.is_here():
            if all(var in self.url for var in ("error=1", "$flink")):
                # when login or password is incorrect they redirect us to login page but with $flink at the end of url
                # and when this is present, error message is not there, we remove it and reload page to get it
                self.location(self.url.replace("$flink", ""))
            error = self.page.get_error()
            if error and "mot de passe" in error:
                raise BrowserIncorrectPassword(error)
            if error and "reeconnecter" in error:
                raise BrowserUnavailable(error)
            raise AssertionError('Unhandled behavior at login: error is "{}"'.format(error))

        elif self.documents.is_here():
            self.email = self.username
            self.status = "inactive"

    @need_login
    def get_subscription_list(self):
        if self.console.is_here():
            # user is logged but has no subscription, he didn't activated anything, there is nothing to return
            return []

        if self.suivi.is_here():
            # user has subscribed recently and his subscription is still being processed
            return []

        self.urlid = self.page.url.rsplit(".pl", 2)[1]
        if self.status == "inactive":
            return self.documents.stay_or_go(urlid=self.urlid).get_list()
        return self.home.stay_or_go(urlid=self.urlid).get_list()

    @need_login
    def iter_documents(self, subscription):
        self.contracts.stay_or_go(urlid=self.urlid)
        contracts_iterator = sorted_documents(self.page.iter_documents(subscription_id=subscription.id))

        self.documents.stay_or_go(urlid=self.urlid)
        bills_iterator = sorted_documents(self.page.get_documents(subid=subscription.id))

        for doc in merge_iterators(contracts_iterator, bills_iterator):
            yield doc

    @need_login
    def get_profile(self):
        # To be sure to load the urlid
        subscriptions = list(self.get_subscription_list())

        self.profile.go(urlid=self.urlid)
        profile = self.page.get_profile(subscriber=subscriptions[0].subscriber)

        self.address.go(urlid=self.urlid)
        self.page.set_address(profile)

        return profile
