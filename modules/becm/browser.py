# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Julien Veyssier
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

from woob.browser.browsers import AbstractBrowser
from woob.browser.profiles import Wget
from woob.browser.url import URL
from woob.browser.browsers import need_login
from woob.exceptions import BrowserIncorrectPassword

from .pages import AdvisorPage, LoginPage, DecoupledStatePage, CancelDecoupled


__all__ = ['BECMBrowser']


class BECMBrowser(AbstractBrowser):
    PROFILE = Wget()
    TIMEOUT = 30
    PARENT = 'creditmutuel'

    HAS_MULTI_BASEURL = True  # Some of the users will use CreditMutuel's BASEURL when others will use becm.fr

    login = URL('/fr/authentification.html', LoginPage)
    advisor = URL('/fr/banques/Details.aspx\?banque=.*', AdvisorPage)

    alternative_decoupled_state = URL(r'/(?P<subbank>.*)fr/otp/SOSD_OTP_GetTransactionState.htm', DecoupledStatePage)
    alternative_cancel_decoupled = URL(r'/(?P<subbank>.*)fr/otp/SOSD_OTP_CancelTransaction.htm', CancelDecoupled)

    def init_login(self):
        # We use by default the creditmutuel's BASEURL, with the 'currentSubBank' logic.
        # But it's not always the correct one for all users.
        # If we hit WRONG_BROWSER_EXCEPTION, we change the BASEURL and some URLs and retry the login.
        try:
            super().init_login()
        except self.WRONG_BROWSER_EXCEPTION:
            self.BASEURL = 'https://www.becm.fr'

            if self.decoupled_state == self.alternative_decoupled_state:
                # to avoid infinite loops
                # if the if is True it means that this isn't the first time we get the exception
                # there's no point in continuing
                raise BrowserIncorrectPassword()

            # We keep the (?P<subbank>.*) and setcurrentSubBank to an empty string
            # to minimize changes to the parents module code and avoid UrlNotResolvable errors
            self.currentSubBank = ''

            # switching the parents urls to this domains (https://www.becm.fr) specific urls
            self.decoupled_state = self.alternative_decoupled_state
            self.cancel_decoupled = self.alternative_cancel_decoupled

            # redo login
            super().init_login()

    @need_login
    def get_advisor(self):
        advisor = None
        if not self.is_new_website:
            self.accounts.stay_or_go(subbank=self.currentSubBank)
            if self.page.get_advisor_link():
                advisor = self.page.get_advisor()
                self.location(self.page.get_advisor_link()).page.update_advisor(advisor)
        else:
            advisor = self.new_accounts.stay_or_go(subbank=self.currentSubBank).get_advisor()
            link = self.page.get_agency()
            if link:
                self.location(link)
                self.page.update_advisor(advisor)
        return iter([advisor]) if advisor else iter([])
