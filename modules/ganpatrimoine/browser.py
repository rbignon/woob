# Copyright(C) 2012-2021  Budget Insight
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

import re
from urllib.parse import parse_qsl, urlparse

from requests.exceptions import ReadTimeout, Timeout

from woob.browser import URL, need_login
from woob.browser.exceptions import HTTPNotFound, ServerError
from woob.browser.mfa import TwoFactorBrowser
from woob.capabilities.bank import Account
from woob.capabilities.base import empty
from woob.exceptions import (
    ActionNeeded,
    ActionType,
    AuthMethodNotImplemented,
    BrowserIncorrectPassword,
    BrowserUnavailable,
    OTPSentType,
    SentOTPQuestion,
)
from woob.tools.capabilities.bank.transactions import sorted_transactions
from woob.tools.decorators import retry

from .pages import (
    AccountDetailsPage,
    AccountDetailsPageBis,
    AccountsPage,
    HistoryPage,
    HomePage,
    LifeInsurancePage,
    LifeInsurancePageInvestmentsDetails,
    LoginPage,
    ProfilePage,
    RibPage,
    RootPage,
    WPSAccountsPage,
    WPSPortalPage,
)


__all__ = ["GanPatrimoineBrowser"]


class GanPatrimoineBrowser(TwoFactorBrowser):
    HAS_CREDENTIALS_ONLY = True

    root_page = URL(r"/$", RootPage)
    login = URL(r"https://authentification.(?P<website>.*).fr/auth/realms", LoginPage)
    home = URL(r"/front", HomePage)
    accounts = URL(r"api/ecli/dossierclient/api/v2/contrats", AccountsPage)
    account_details = URL(r"/api/v1/contrats/(?P<account_id>.*)", AccountDetailsPage)
    account_details_bis = URL(r"/api/ecli/dossierclient/api/v1/contrats/(?P<account_id>.*)", AccountDetailsPageBis)
    history = URL(r"/api/ecli/vie/historique", HistoryPage)
    profile_page = URL(r"/api/v1/utilisateur", ProfilePage)
    wps_dashboard = URL(r"/wps/myportal/TableauDeBord", WPSAccountsPage)
    rib_page = URL(r"/wps/myportal/.*/res/id=QCPDetailRib.jsp", RibPage)
    wps_portal = URL("/wps/myportal/!ut/", WPSPortalPage)

    # URLs for some life insurance contracts are on a different website
    LIFE_INSURANCE_URL = "https://www.contrat-groupe-ganassurances.fr"
    life_insurances_private = URL(
        r"/lib/aspx/EspacePrive/Salarie/TableauDeBord.aspx", LifeInsurancePage, base="LIFE_INSURANCE_URL"
    )
    life_insurances_details = URL(
        r"/lib/aspx/EspacePrive/Salarie/Retraite_UC/Epargne.aspx\?ct=",
        LifeInsurancePageInvestmentsDetails,
        base="LIFE_INSURANCE_URL",
    )

    def __init__(self, website, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.website = website
        self.BASEURL = "https://espaceclient.%s.fr" % website
        self.has_otp = False

        self.AUTHENTICATION_METHODS = {
            "otp_sms": self.handle_sms,
        }

    def handle_sms(self):
        self.page.post_2fa_form(self.otp_sms)
        if self.login.is_here():
            if self.page.has_strong_authentication():
                raise BrowserIncorrectPassword(bad_fields="otp_sms")
            raise AssertionError("Unexpected error at login")

    def init_login(self):
        if self.has_otp:
            # If mfa is enable we will not be able
            # to abort login before the sms is sent.
            self.check_interactive()

        try:
            self.location(self.BASEURL)
        except Timeout:
            # We assume that the website is under maintenance/down
            raise BrowserUnavailable("Espace client indisponible")

        if self.root_page.is_here() and self.page.is_website_unavailable():
            raise BrowserUnavailable("Espace client indisponible")

        # This part is necessary for a child module with a different login URL.
        if not self.login.is_here():
            query = urlparse(self.url).query
            self.login.go(params=parse_qsl(query))

        self.page.login(self.username, self.password)

        self.has_otp = False
        if self.login.is_here():
            if self.page.has_strong_authentication():
                # SMS is already send, we can't stop it
                self.has_otp = True
                raise SentOTPQuestion(
                    "otp_sms",
                    medium_type=OTPSentType.SMS,
                    medium_label=self.page.get_otp_phone_number(),
                    message=self.page.get_otp_message(),
                )

            error_message = self.page.get_error_message()
            if "Vous utilisez un navigateur qui n'est plus supporté par notre site" in error_message:
                # Can't explain why, but we are encountering this page when a SCA is needed.
                # Here, there is a "continuer le processus" link that go to the SCA page
                # that send the SMS directly without asking.
                raise AuthMethodNotImplemented()

            if any(
                (
                    "Identifiant ou mot de passe incorrect" in error_message,
                    "3 essais infructueux" in error_message,
                )
            ):
                raise BrowserIncorrectPassword(error_message)

            if "Vous devez vous connecter avec votre numéro client" in error_message:
                raise BrowserIncorrectPassword(error_message, bad_fields=["login"])

            unavailable_error = re.compile("Erreur inattendue|Problème technique")
            if unavailable_error.search(error_message):
                raise BrowserUnavailable()

            if "Erreur de connexion" in error_message and self.page.is_wrongpass():
                raise BrowserIncorrectPassword()

            if "Connexion non autorisée" in error_message:
                raise ActionNeeded(error_message)

            if "Oups ! Numéro de mobile absent" in error_message:
                raise ActionNeeded(
                    locale="fr-FR",
                    message="Votre espace client requiert l'ajout d'un numéro de téléphone",
                    action_type=ActionType.ENABLE_MFA,
                )

            assert False, "Unhandled error at login: %s" % error_message

    @need_login
    def iter_accounts(self):
        self.accounts.go()

        for account in self.page.iter_accounts():
            try:
                retry(ReadTimeout)(self.account_details.go)(account_id=account.id.lower())
            except HTTPNotFound:
                # Some accounts have no available detail on the new website,
                # the server then returns a 404 error
                self.logger.warning(
                    "No available detail for account n°%s on the new website, it will be skipped.", account.id
                )
                continue

            # We must deal with different account categories differently
            # because the JSON content depends on the account category.
            if account._category == "compte bancaire":
                self.page.fill_account(obj=account)
                # JSON of checking accounts may contain deferred cards
                for card in self.page.iter_cards():
                    card.parent = account
                    card._url = account._url
                    yield card

            elif account._category in ("epargne bancaire", "compte titres", "certificat mutualiste"):
                self.page.fill_account(obj=account)

            elif account._category == "crédit":
                self.page.fill_loan(obj=account)

            elif account._category in ("epargne", "retraite"):
                self.page.fill_wealth_account(obj=account)
                if account.balance and self.page.has_investments():
                    # Some life insurances have no investments
                    for inv in self.page.iter_investments():
                        account._investments.append(inv)

                # We check another API route to fetch the balance.
                # Hypothesis : Contracts with 'incomplete' set as True (in AccountsPage JSON)
                # maybe be the only ones concerned by this. (We cannot be sure at this point
                # so we handle this by checking if the balance is missing).
                if empty(account.balance):
                    self.account_details_bis.go(account_id=account.id.lower())
                    self.page.fill_wealth_account(obj=account)
                    # No investments available on this route.

                # Some accounts have their details available on an external GAN website.
                if empty(account.balance):
                    self.location(account._url)
                    if self.life_insurances_private.is_here():
                        self.page.load_data()
                        self.page.fill_account(obj=account)

                        self.location(self.page.get_details_url())
                        self.page.load_details()
                        self.page.fill_account(obj=account)

                        # Since it takes time to access this space, we fetch investments and history for later.
                        account._investments = list(self.page.iter_investments())

            elif account._category == "autre":
                # This category contains PEE and PERP accounts for example.
                # They may contain investments.
                self.page.fill_wealth_account(obj=account)

            else:
                self.logger.warning(
                    "Category %s is not handled yet, account n°%s will be skipped.", account._category, account.id
                )
                continue

            if empty(account.balance):
                self.logger.warning("Could not fetch the balance for account n°%s, it will be skipped.", account.id)
                continue

            yield account

    @need_login
    def iter_investment(self, account):
        if account._category not in ("epargne", "retraite", "autre"):
            return

        return account._investments

    @need_login
    def iter_history(self, account):
        param_categories = {
            "Compte bancaire": "COMPTE_COURANT",
            "Epargne bancaire": "EPARGNE",
            "Retraite": "RETRAITE",
            "Epargne": "EPARGNE",
            "Crédit": "CREDIT",
            "Carte": "CARTE",
            "Compte titres": "COMPTE_TITRES",
            "Certificat mutualiste": "C_MUTUALISTE",
            "Autre": "AUTRE",
        }

        if account._category not in param_categories:
            self.logger.warning("History is not yet handled for category %s.", account._category)
            return

        if account._url:
            if account.type != Account.TYPE_CARD:
                self.location(account._url)
                if self.wps_dashboard.is_here():
                    detail_url = self.page.get_account_history_url(account.id)
                    self.location(detail_url, data="")
                    yield from self.page.iter_history(account_id=account.id)
        else:

            params = {
                "identifiantContrat": account.id.lower(),
                "familleProduit": param_categories[account._category],
            }
            try:
                self.history.go(params=params)
            except ServerError:
                # Some checking accounts and deferred cards do not have
                # an available history on the new website yet.
                raise BrowserUnavailable()

            # Transactions are sorted by category, not chronologically
            yield from sorted_transactions(self.page.iter_wealth_history())

    @need_login
    def iter_coming(self, account):
        if account._url and account.type == Account.TYPE_CARD:
            self.location(account._url)
            if self.wps_dashboard.is_here():
                detail_url = self.page.get_account_history_url(account.id[-6:])
                self.location(detail_url, data="")
                yield from self.page.iter_card_history()

    @need_login
    def get_profile(self):
        # Note, profile could eventually be extended with email and address
        # by using: https://espaceclient.groupama.fr/api/v1/utilisateur/contacts?favorite=true&emails=true&telephones=false&adresses=true
        self.profile_page.go()
        return self.page.get_profile()
