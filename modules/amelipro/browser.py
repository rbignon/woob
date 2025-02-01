# Copyright(C) 2022      Powens

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

import string
from datetime import date
from random import choices

from dateutil.relativedelta import relativedelta

from woob.browser import URL, LoginBrowser, need_login
from woob.capabilities.captcha import ImageCaptchaQuestion
from woob.exceptions import BrowserIncorrectPassword, WrongCaptchaResponse
from woob.tools.capabilities.bill.documents import merge_iterators

from .pages import AuthorizationPage, DocumentsDetailsPage, DocumentsSummaryPage, LotPDF, RelevePDF, SubscriptionPage


__all__ = ["AmeliProBrowser"]


class AmeliProBrowser(LoginBrowser):
    BASEURL = "https://paiements2.ameli.fr"

    login_page = URL(r"https://authps-espacepro.ameli.fr/oauth2/authorize", AuthorizationPage)
    subscription_page = URL(
        r"https://espacepro.ameli.fr/PortailPS/appmanager/portailps/professionnelsante", SubscriptionPage
    )
    documents_summary_page = URL(r"/api/hdpam/releve-mensuel/releve-compte/liste\?doTrack=false", DocumentsSummaryPage)
    documents_details_page = URL(r"/api/hdpam/tiers-payant/resume-lots/recherche-date-paiement", DocumentsDetailsPage)
    releve_pdf_url = URL(r"/api/hdpam/releve-mensuel/releve-compte/telecharger", RelevePDF)
    # "lot" regroups some detailled bills depending on their administrative jurisdiction
    lot_pdf_url = URL(r"/api/hdpam/tiers-payant/details/pdfDetailLot", LotPDF)

    def __init__(self, config, *args, **kwargs):
        self.config = config
        super().__init__(*args, **kwargs)

    def do_login(self):
        # login_page redirects us to the same page but it adds many auth params in the URL
        # POST with authentication data must be done on that specific URL
        if self.config["captcha_response"].get():
            if self.login_page.is_here():
                data = self.page.get_post_data()
                data.update(
                    {
                        "lmAuth": "login",
                        "user": self.username,
                        "password": self.password,
                        "captcha_user_code": self.config["captcha_response"].get(),
                    }
                )
                self.location(self.url, data=data)
            else:
                raise AssertionError("Not on login page after captcha solving, URL is %s" % self.url)

        else:
            self.login_page.go()
            captcha_url = self.page.get_captcha_url()
            image = self.open(captcha_url).content
            raise ImageCaptchaQuestion(image)

        if self.login_page.is_here():
            message = self.page.get_error_message()
            if "failed at typing the captcha" in message:
                raise WrongCaptchaResponse()
            if "identifiant ou mot de passe est incorrect" in message:
                raise BrowserIncorrectPassword()
            raise AssertionError("Unhandled error during login: %s" % message)

    @need_login
    def iter_subscription(self):
        params = {
            "_nfpb": "true",
            "_pageLabel": "vp_accueil_page",
        }
        self.subscription_page.go(params=params)
        yield self.page.get_subscription()

    @need_login
    def _iter_summary_documents(self, subscription):
        # GET request on the BASEURL mandatory here or
        # we'll have a 401 later while trying to access
        # summary or details documents
        self.go_home()
        self.documents_summary_page.go()
        return self.page.iter_documents(subid=subscription.id)

    @need_login
    def _iter_details_documents(self, subscription):
        # correlation_id can be randomly generated but is needed
        # to access details documents or we get a 401
        correlation_id = "".join(choices(string.digits, k=10))
        self.session.headers["correlationID"] = correlation_id

        today = date.today()
        params = {
            "dateDebutPaiement": today - relativedelta(years=1),
            "dateFinPaiement": today,
            "doTrack": "False",
        }
        self.documents_details_page.go(params=params)

        return self.page.iter_documents(subid=subscription.id)

    @need_login
    def iter_documents(self, subscription):
        return merge_iterators(
            self._iter_summary_documents(subscription),
            self._iter_details_documents(subscription),
        )
