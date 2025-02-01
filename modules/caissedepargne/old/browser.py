# Copyright(C) 2012 Romain Bignon
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
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlparse

from dateutil import parser, tz
from requests.cookies import remove_cookie_by_name

from woob.browser.browsers import need_login
from woob.browser.exceptions import ClientError, LoggedOut, ServerError
from woob.browser.retry import retry_on_logout
from woob.browser.url import URL
from woob.capabilities.bank import Account, Transaction
from woob.capabilities.base import NotAvailable, find_object
from woob.capabilities.profile import Profile
from woob.exceptions import BrowserHTTPError, BrowserUnavailable
from woob.tools.capabilities.bank.investments import create_french_liquidity
from woob.tools.capabilities.bank.transactions import (
    FrenchTransaction,
    keep_only_card_transactions,
    omit_deferred_transactions,
    sorted_transactions,
)
from woob.tools.date import now_as_utc
from woob.tools.decorators import retry
from woob.tools.json import json
from woob_modules.linebourse.browser import LinebourseAPIBrowser

from ..browser import CaisseEpargneLogin
from .pages import (
    ActivationSubscriptionPage,
    AuthentPage,
    CardsComingPage,
    CardsOldWebsitePage,
    CardsPage,
    ConsLoanPage,
    CreditCooperatifMarketPage,
    GarbagePage,
    IndexPage,
    LifeInsurance,
    LifeInsuranceHistory,
    LifeInsuranceInvestments,
    LoadingPage,
    MarketPage,
    MeasurePage,
    MessagePage,
    NatixisErrorPage,
    NatixisLIHis,
    NatixisLIInv,
    NatixisRedirectPage,
    NewLeviesPage,
    OldLeviesPage,
    TechnicalIssuePage,
    TransactionPopupPage,
    TransactionsDetailsPage,
    UnavailablePage,
)


__all__ = ["OldCaisseEpargneBrowser"]


def decode_utf8_cookie(data):
    # caissedepargne/palatine cookies may contain non-ascii bytes which is ill-defined.
    # Actually, they use utf-8.
    # Since it's not standard, requests/urllib interprets it freely... as latin-1
    # and we can't really blame for that.
    # Let's decode this shit ourselves.
    return data.encode("latin-1").decode("utf-8")


class OldCaisseEpargneBrowser(CaisseEpargneLogin):
    BASEURL = "https://www.caisse-epargne.fr"
    HISTORY_MAX_PAGE = 200
    TIMEOUT = 60

    LINEBOURSE_BROWSER = LinebourseAPIBrowser

    loading = URL(r"https://.*/CreditConso/ReroutageCreditConso.aspx", LoadingPage)
    revolving_details = URL(
        r"https://www.credit-conso-cr.caisse-epargne.fr/websavcr-web/rest/contrat/getContrat", ConsLoanPage
    )
    cons_details = URL(
        r"https://www.credit-conso-pp.caisse-epargne.fr/websavpp-web/rest/contrat/getInfoContrat", ConsLoanPage
    )
    cons_details_form = URL(r"https://www.net.*.caisse-epargne.fr/CreditConso/ReroutageSAV_PP.aspx", IndexPage)
    transaction_detail = URL(r"https://.*/Portail.aspx.*", TransactionsDetailsPage)
    measure_page = URL(r"https://.*/Portail.aspx.*", MeasurePage)
    cards_old = URL(r"https://.*/Portail.aspx.*", CardsOldWebsitePage)
    cards = URL(r"https://.*/Portail.aspx.*", CardsPage)
    cards_coming = URL(r"https://.*/Portail.aspx.*", CardsComingPage)
    old_checkings_levies = URL(r"https://.*/Portail.aspx.*", OldLeviesPage)
    new_checkings_levies = URL(r"https://.*/Portail.aspx.*", NewLeviesPage)
    authent = URL(r"https://.*/Portail.aspx.*", AuthentPage)
    activation_subscription = URL(r"https://.*/Portail.aspx.*", ActivationSubscriptionPage)
    transaction_popup = URL(r"https://.*/Portail.aspx.*", TransactionPopupPage)
    market = URL(
        r"https://.*/Pages/Bourse.*",
        r"https://www.caisse-epargne.offrebourse.com/ReroutageSJR",
        r"https://www.caisse-epargne.offrebourse.com/fr/6CE.*",
        r"https://www.caisse-epargne.offrebourse.com/app-v2/#/app-mobile",
        MarketPage,
    )
    unavailable_page = URL(r"https://www.caisse-epargne.fr/.*/au-quotidien", UnavailablePage)

    creditcooperatif_market = URL(
        r"https://www.offrebourse.com/.*", CreditCooperatifMarketPage
    )  # just to catch the landing page of the Credit Cooperatif's Linebourse
    life_insurance_history = URL(
        r"https://www.extranet2.caisse-epargne.fr/cin-front/contrats/evenements", LifeInsuranceHistory
    )
    life_insurance_investments = URL(
        r"https://www.extranet2.caisse-epargne.fr/cin-front/contrats/details", LifeInsuranceInvestments
    )
    life_insurance = URL(
        r"https://.*/Assurance/Pages/Assurance.aspx", r"https://www.extranet2.caisse-epargne.fr.*", LifeInsurance
    )

    natixis_redirect = URL(
        r"/NaAssuranceRedirect/NaAssuranceRedirect.aspx",
        # TODO: adapt domain to children of CE
        r"https://www.espace-assurances.caisse-epargne.fr/espaceinternet-ce/views/common/routage-itce.xhtml",
        NatixisRedirectPage,
    )
    natixis_life_ins_his = URL(
        # TODO: adapt domain to children of CE
        r"https://www.espace-assurances.caisse-epargne.fr/espaceinternet-ce/rest/v2/contratVie/load-operation(?P<account_path>)",
        NatixisLIHis,
    )
    natixis_life_ins_inv = URL(
        # TODO: adapt domain to children of CE
        r"https://www.espace-assurances.caisse-epargne.fr/espaceinternet-ce/rest/v2/contratVie/load(?P<account_path>)",
        NatixisLIInv,
    )
    natixis_error = URL(
        # TODO: adapt domain to children of CE
        r"https://www.espace-assurances.caisse-epargne.fr/espaceinternet-ce/page500.xhtml",
        NatixisErrorPage,
    )

    message = URL(r"https://www.caisse-epargne.offrebourse.com/DetailMessage\?refresh=O", MessagePage)
    home = URL(r"https://.*/Portail.aspx.*", IndexPage)
    home_tache = URL(r"https://.*/Portail.aspx\?tache=(?P<tache>).*", IndexPage)
    garbage = URL(
        r"https://www.caisse-epargne.offrebourse.com/Portefeuille",
        r"https://www.caisse-epargne.fr/particuliers/.*/emprunter.aspx",
        r"https://.*/particuliers/emprunter.*",
        r"https://.*/particuliers/epargner.*",
        r"https://www.caisse-epargne.fr/.*/epargner",
        GarbagePage,
    )

    tech_issue = URL(r"https://.*/erreur_technique", TechnicalIssuePage)

    # Accounts managed in life insurance space (not in linebourse)

    insurance_accounts = (
        "AIKIDO",
        "ASSURECUREUIL",
        "ECUREUIL PROJET",
        "GARANTIE RETRAITE EU",
        "INITIATIVES PLUS",
        "INITIATIVES TRANSMIS",
        "LIVRET ASSURANCE VIE",
        "OCEOR EVOLUTION",
        "PATRIMONIO CRESCENTE",
        "PEP TRANSMISSION",
        "PERP",
        "PERSPECTIVES ECUREUI",
        "POINTS RETRAITE ECUR",
        "RICOCHET",
        "SOLUTION PERP",
        "TENDANCES",
        "YOGA",
    )

    def __init__(self, nuser, config, *args, **kwargs):
        self.accounts = None
        self.loans = None
        self.cards_not_reached = False
        self.typeAccount = None
        self.inexttype = 0  # keep track of index in the connection type's list
        self.recipient_form = None
        self.is_send_sms = None
        self.is_use_emv = None
        self.market_url = kwargs.pop(
            "market_url",
            "https://www.caisse-epargne.offrebourse.com",
        )
        self.has_subscription = True

        super().__init__(nuser, config, *args, **kwargs)

        self.__states__ += (
            "recipient_form",
            "is_send_sms",
            "is_app_validation",
            "is_use_emv",
            "new_website",
            "cards_not_reached",
        )
        dirname = self.responses_dirname
        if dirname:
            dirname += "/bourse"

        self.linebourse = self.LINEBOURSE_BROWSER(
            self.market_url,
            logger=self.logger,
            responses_dirname=dirname,
            proxy=self.PROXIES,
        )

    def load_state(self, state):
        expire = state.get("expire")
        if expire:
            expire = parser.parse(expire)
            if not expire.tzinfo:
                expire = expire.replace(tzinfo=tz.tzlocal())
            if expire < now_as_utc():
                self.logger.info("State expired, not reloading it from storage")
                return

        # TODO: Always loading the state might break something.
        # if 'login_otp_validation' in state and state['login_otp_validation'] is not None:
        #    super(CaisseEpargne, self).load_state(state)

        super().load_state(state)

    def locate_browser(self, state):
        # after entering the emv otp the locate browser is making a request on
        # the last url we visited, and in that case we are invalidating the
        # validation_unit_id needed for sending the otp
        if any((self.config["otp_emv"].get(), self.config["otp_sms"].get())):
            return

        try:
            super().locate_browser(state)
        except LoggedOut:
            # If the cookies are expired (it's not clear for how long they last),
            # we'll get redirected to the LogoutPage which will raise a LoggedOut.
            # So we catch it and the login process will start.
            pass

    def deleteCTX(self):
        # For connection to offrebourse and natixis, we need to delete duplicate of CTX cookie
        if len([k for k in self.session.cookies.keys() if k == "CTX"]) > 1:
            del self.session.cookies["CTX"]

    def do_login(self):
        self.browser_switched = True
        super().do_login()
        return

    def go_details_revolving_or_cons(self, loan_type):
        days = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
        month = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
        now = datetime.today()
        # for non-DST
        # d = '%s %s %s %s %s:%s:%s GMT+0100 (heure normale d’Europe centrale)' % (days[now.weekday()], now.day, month[now.month - 1], now.year, now.hour, format(now.minute, "02"), now.second)
        # TODO use babel library to simplify this code
        d = "{} {} {} {} {}:{}:{} GMT+0200 (heure d’été d’Europe centrale)".format(
            days[now.weekday()],
            now.day,
            month[now.month - 1],
            now.year,
            now.hour,
            format(now.minute, "02"),
            now.second,
        )

        if self.home.is_here():
            msg = self.page.loan_unavailable_msg()
            if msg:
                self.logger.warning("%s" % msg)
                return None
        if loan_type == "cons":
            message = self.page.get_partial_accounts_error_message()
            if message:
                raise BrowserUnavailable(message)

            self.page.submit_conso_details()
            self.cons_details.go(params={"datePourIE": d})
        elif loan_type == "revolving":
            self.revolving_details.go(params={"datePourIE": d})

        return self.page.get_conso()

    def go_measure_list(self, page_num=0):
        self.home.go()

        if not self.measure_page.is_here():
            raise AssertionError("Should be on measure_page")

        self.page.go_measure_list()
        for _ in range(page_num):
            self.page.goto_next_page()

    def get_owner_name(self):
        # Get name from profile to verify who is the owner of accounts.
        name = self.get_profile().name.upper().split(" ", 1)
        if len(name) == 2:  # if the name is complete (with first and last name)
            owner_name = name[1]
        else:  # if there is only first name
            owner_name = name[0]
        return owner_name

    def get_accounts(self, owner_name):
        self.page.check_no_accounts()
        accounts = []
        for page_num in range(20):
            for measure_id in self.page.get_measure_ids():
                self.page.go_measure_accounts_list(measure_id)
                if self.page.check_measure_accounts():
                    for new_account in self.page.get_list(owner_name):
                        # joint accounts can be present twice, once per owner
                        if new_account.id in [account.id for account in accounts]:
                            self.logger.warning("Skip the duplicate account, id :  %s" % new_account.id)
                            continue

                        new_account._info["measure_id"] = measure_id
                        new_account._info["measure_id_page_num"] = page_num
                        accounts.append(new_account)

                self.go_measure_list(page_num)

            if not self.page.has_next_page():
                break
            self.page.goto_next_page()
        return accounts

    @need_login
    def get_measure_accounts_list(self):
        """
        On home page there is a list of "measure" links, each one leading to one person accounts list.
        Iter over each 'measure' and navigate to it to get all accounts
        """
        self.home.go()

        if self.tech_issue.is_here():
            raise BrowserUnavailable()

        owner_name = self.get_owner_name()
        # Make sure we are on list of measures page
        if self.measure_page.is_here():
            self.accounts = self.get_accounts(owner_name)

            for account in self.accounts:
                if "acc_type" in account._info and account._info["acc_type"] == Account.TYPE_LIFE_INSURANCE:
                    self.go_measure_list(account._info["measure_id_page_num"])
                    self.page.go_measure_accounts_list(account._info["measure_id"])
                    self.page.go_history(account._info)

                    if self.message.is_here():
                        self.page.submit()
                        self.page.go_history(account._info)

                    balance = self.page.get_measure_balance(account)
                    account.balance = Decimal(FrenchTransaction.clean_amount(balance))
                    account.currency = account.get_currency(balance)

        return self.accounts

    def update_linebourse_token(self):
        assert self.linebourse is not None, "linebourse browser should already exist"
        self.linebourse.session.cookies.update(self.session.cookies)
        # It is important to fetch the domain dynamically because
        # for caissedepargne the domain is 'www.caisse-epargne.offrebourse.com'
        # whereas for creditcooperatif it is 'www.offrebourse.com'
        domain = urlparse(self.url).netloc
        self.linebourse.session.headers["X-XSRF-TOKEN"] = self.session.cookies.get("XSRF-TOKEN", domain=domain)

    def add_linebourse_accounts_data(self):
        for account in self.accounts:
            self.deleteCTX()
            if account.type in (Account.TYPE_MARKET, Account.TYPE_PEA):
                self.home_tache.go(tache="CPTSYNT0")
                self.page.go_history(account._info)

                if self.message.is_here():
                    self.page.submit()
                    self.page.go_history(account._info)

                # Some users may not have access to this.
                if not self.market.is_here():
                    continue
                self.page.submit()

                if "offrebourse.com" in self.url:
                    # Some users may not have access to this.
                    if self.page.is_error():
                        continue

                    self.update_linebourse_token()
                    page = self.linebourse.go_portfolio(account.id)
                    assert self.linebourse.portfolio.is_here()
                    # We must declare "page" because this URL also matches MarketPage
                    account.valuation_diff = page.get_valuation_diff()

                    # We need to go back to the synthesis, else we can not go home later
                    self.home_tache.go(tache="CPTSYNT0")
                else:
                    raise AssertionError("new domain that hasn't been seen so far?")

    def add_card_accounts(self):
        """
        Card cases are really tricky on the new website.
        There are 2 kinds of page where we can find cards information
            - CardsPage: List some of the PSU cards
            - CardsComingPage: On the coming transaction page (for a specific checking account),
                we can find all cards related to this checking account. Information to reach this
                CC is in the home page

        We have to go through this both kind of page for those reasons:
                - If there is no coming yet, the card will not be found in the home page and we will not
                be able to reach the CardsComingPage. But we can find it on CardsPage
                - Some cards are only on the CardsComingPage and not the CardsPage
                - In CardsPage, there are cards (with "Business" in the label) without checking account on the
                website (neither history nor coming), so we skip them.
                - Some card on the CardsPage that have a checking account parent, but if we follow the link to
                reach it with CardsComingPage, we find an other card that is not in CardsPage.
        """
        if self.new_website:
            for account in self.accounts:
                # Adding card's account that we find in CardsComingPage of each Checking account
                if account._card_links:
                    self.home.go()
                    self.page.go_history(account._card_links)
                    is_id_duplicate = self.page.is_id_duplicate()
                    for card in self.page.iter_cards(is_id_duplicate=is_id_duplicate):
                        card.parent = account
                        card._coming_info = self.page.get_card_coming_info(card.number, card.parent._card_links.copy())
                        card.ownership = account.ownership
                        card.owner_type = account.owner_type
                        self.accounts.append(card)

        self.home.go()
        self.page.go_list()
        self.page.go_cards()

        # We are on the new website. We already added some card, but we can find more of them on the CardsPage
        if self.cards.is_here():
            for card in self.page.iter_cards():
                card.parent = find_object(self.accounts, number=card._parent_id)
                if not card.parent:
                    self.logger.info(f"The parent {card._parent_id} of the card {card.id} wasn't found.")
                    continue

                card.owner_type = card.parent.owner_type

                # If we already added this card, we don't have to add it a second time
                if find_object(self.accounts, number=card.number):
                    continue

                info = card.parent._card_links

                # If card.parent._card_links is not filled, it mean this checking account
                # has no coming transactions.
                card._coming_info = None
                card.ownership = card.parent.ownership
                if info:
                    self.page.go_list()
                    self.page.go_history(info)
                    card._coming_info = self.page.get_card_coming_info(card.number, info.copy())

                    if not card._coming_info:
                        self.logger.warning("Skip card %s (not found on checking account)", card.number)
                        continue
                self.accounts.append(card)

        # We are on the old website. We add all card that we can find on the CardsPage
        elif self.cards_old.is_here():
            for card in self.page.iter_cards():
                card.parent = find_object(self.accounts, number=card._parent_id)
                assert card.parent, "card account parent %s was not found" % card.number
                card.owner_type = card.parent.owner_type
                self.accounts.append(card)

    def add_owner_accounts(self):
        owner_name = self.get_owner_name()

        if self.home.is_here():
            self.page.check_no_accounts()
            self.page.go_list()
        else:
            self.home.go()

        self.accounts = list(self.page.get_list(owner_name))

        try:
            # Get wealth accounts that are not on the summary page
            self.home_tache.go(tache="EPASYNT0")
            # If there are no wealth accounts we are redirected to the "garbage page"
            if self.home.is_here():
                for account in self.page.get_list(owner_name):
                    if account.id not in [acc.id for acc in self.accounts]:
                        if account.type == Account.TYPE_LIFE_INSURANCE and "MILLEVIE" not in account.label:
                            # For life insurance accounts, we check if the contract is still open,
                            # Except for MILLEVIE insurances, because the flow is different
                            # and we can't check at that point.
                            if not self.go_life_insurance_investments(account):
                                continue
                            if self.page.is_contract_closed():
                                continue
                        self.accounts.append(account)
            wealth_not_accessible = False

        except ServerError:
            self.logger.warning("Could not access wealth accounts page (ServerError)")
            wealth_not_accessible = True
        except ClientError as e:
            resp = e.response
            if resp.status_code == 403 and "Ce contenu n'existe pas." in resp.text:
                self.logger.warning("Could not access wealth accounts page (ClientError)")
                wealth_not_accessible = True
            else:
                raise

        if wealth_not_accessible:
            # The navigation can be broken here
            # We first check if we are logout
            # and if it is the case we do login again
            try:
                # if home.go reached LogoutPage,
                # LoggedOut exception avoids to finish add_owner_accounts()
                # and add_card_accounts() must be done after the next do_login
                self.cards_not_reached = True
                self.home.go()
            except BrowserUnavailable:
                if not self.error.is_here():
                    raise
                self.do_login()
                self.cards_not_reached = False

        self.add_linebourse_accounts_data()
        self.add_card_accounts()

    def check_accounts_exist(self):
        """
        Sometimes for connections that have no accounts we get stuck in the `ActivationSubscriptionPage`.
        The `check_no_accounts` inside the `get_measure_accounts_list` is never reached.
        """
        self.home.go()
        if not self.activation_subscription.is_here():
            return
        self.page.send_check_no_accounts_form()
        assert self.activation_subscription.is_here(), "Expected to be on ActivationSubscriptionPage"
        self.page.check_no_accounts()

    def iter_accounts(self):
        self.BASEURL = "https://" + urlparse(self.continue_url).netloc
        accounts = self.get_accounts_list()
        accounts.extend(self.get_loans_list())
        return accounts

    @retry_on_logout()
    @need_login
    @retry(ClientError, tries=3)
    def get_accounts_list(self):
        self.check_accounts_exist()

        if self.accounts is None:
            self.accounts = self.get_measure_accounts_list()

        if self.accounts is None:
            self.add_owner_accounts()

        if self.cards_not_reached:
            # The navigation has been broken during wealth navigation
            # We must finish accounts return with add_card_accounts()
            self.add_card_accounts()
            self.cards_not_reached = False

        # Some accounts have no available balance or label and cause issues
        # in the backend so we must exclude them from the accounts list:
        self.accounts = [account for account in self.accounts if account.label and account.balance != NotAvailable]

        return self.accounts

    @retry_on_logout()
    @need_login
    def get_loans_list(self):
        if self.loans is None:
            self.loans = []

            if self.home.is_here():
                if self.page.check_no_accounts() or self.page.check_no_loans():
                    return []

            for _ in range(2):
                self.home_tache.go(tache="CRESYNT0")
                if self.tech_issue.is_here():
                    raise BrowserUnavailable()

                if self.home.is_here():
                    if not self.page.is_access_error():
                        # The server often returns a 520 error (Undefined):
                        try:
                            self.loans = list(self.page.get_loan_list())
                        except BrowserUnavailable:
                            # The old website often returns errors
                            self.logger.warning("Loan access has failed, which can potentially delete loan account.")
                        except ServerError:
                            self.logger.warning("Access to loans failed, we try again")
                        else:
                            if self.home.is_here() and self.page.is_old_loan_website():
                                for loan in self.loans:
                                    self.page.submit_form(*loan._form_params)
                                    self.page.fill_old_loan(obj=loan)
                            # We managed to reach the Loans JSON
                            break

            for _ in range(3):
                try:
                    self.home_tache.go(tache="CPTSYNT0")

                    if self.home.is_here():
                        self.page.go_list()
                except ClientError:
                    pass
                else:
                    break

        return self.loans

    # For all account, we fill up the history with transaction. For checking account, there will have
    # also deferred_card transaction too.
    # From this logic, if we send "account_card", that mean we recover all transactions from the parent
    # checking account of the account_card, then we filter later the deferred transaction.
    @need_login
    def _get_history(self, info, account_card=None):
        # Only fetch deferred debit card transactions if `account_card` is not None
        if isinstance(info["link"], list):
            info["link"] = info["link"][0]
        if not info["link"].startswith("HISTORIQUE"):
            return
        if "measure_id" in info:
            self.home_tache.go(tache="CPTSYNT0")
            self.go_measure_list(info["measure_id_page_num"])
            self.page.go_measure_accounts_list(info["measure_id"])
        elif self.home.is_here():
            self.page.go_list()
        else:
            self.home_tache.go(tache="CPTSYNT0")

        self.page.go_history(info)

        # ensure we are on the correct history page
        if "netpro" in self.page.url and not self.page.is_history_of(info["id"]):
            self.page.go_history_netpro(info)

        # In this case, we want the coming transaction for the new website
        # (old website return coming directly in `get_coming()` )
        if account_card and info and info["type"] == "HISTORIQUE_CB":
            self.page.go_coming(account_card._coming_info["link"])

        info["link"] = [info["link"]]

        for i in range(self.HISTORY_MAX_PAGE):

            assert self.home.is_here()

            # list of transactions on account page
            transactions_list = []
            card_and_forms = []
            for tr in self.page.get_history():
                transactions_list.append(tr)
                if tr.type == tr.TYPE_CARD_SUMMARY:
                    if account_card:
                        if self.card_matches(tr.card, account_card.number):
                            card_and_forms.append((tr.card, self.page.get_form_to_detail(tr)))
                        else:
                            self.logger.debug(
                                "will skip summary detail (%r) for different card %r", tr, account_card.number
                            )
                elif tr.type == FrenchTransaction.TYPE_CARD and "fac cb" in tr.raw.lower() and not account_card:
                    # for immediate debits made with a def card the label is way too empty for certain clients
                    # we therefore open a popup and find the rest of the label
                    # can't do that for every type of transactions because it makes a lot a additional requests
                    form = self.page.get_form_to_detail(tr)
                    transaction_popup_page = self.open(form.url, data=form)
                    tr.raw += " " + transaction_popup_page.page.complete_label()

            # For deferred card history only :
            #
            # Now that we find transactions that have TYPE_CARD_SUMMARY on the checking account AND the account_card number we want,
            # we browse deferred card transactions that are resume by that list of TYPE_CARD_SUMMARY transaction.

            # Checking account transaction:
            #  - 01/01 - Summary 5134XXXXXX103 - 900.00€ - TYPE_CARD_SUMMARY  <-- We have to go in the form of this tr to get
            #   cards details transactions.
            for card, form in card_and_forms:
                form.submit()
                if self.home.is_here() and self.page.is_access_error():
                    self.logger.warning("Access to card details is unavailable for this user")
                    continue
                assert self.transaction_detail.is_here()
                for tr in self.page.get_detail():
                    tr.type = Transaction.TYPE_DEFERRED_CARD
                    if account_card:
                        tr.card = card
                        tr.bdate = tr.rdate
                    transactions_list.append(tr)
                if self.new_website:
                    self.page.go_newsite_back_to_summary()
                else:
                    self.page.go_form_to_summary()

                # going back to summary goes back to first page
                for _ in range(i):
                    assert self.page.go_next()

            #  order by date the transactions without the summaries
            transactions_list = sorted_transactions(transactions_list)

            for tr in transactions_list:
                yield tr

            assert self.home.is_here()

            if not self.page.go_next():
                return

        raise AssertionError(f"More than {self.HISTORY_MAX_PAGE} history pages")

    @need_login
    def _get_history_invests(self, account):
        if self.home.is_here():
            self.page.go_list()
        else:
            self.home.go()

        if account._info["type"] == "SYNTHESE_EPARGNE":
            # If the type is not SYNTHESE_EPARGNE, it means we have a direct link and going
            # this way would set off a SyntaxError.
            self.page.go_history(account._info)

        if account.type in (Account.TYPE_LIFE_INSURANCE, Account.TYPE_CAPITALISATION, Account.TYPE_PERP):
            if self.page.is_account_inactive(account.id):
                self.logger.warning(f"Account {account.label} {account.id} is inactive.")
                return []

            if "MILLEVIE" in account.label:
                # This way we ensure we can access all type of MILLEVIE accounts
                self.home_tache.go(tache="EPASYNT0")
                self.page.go_life_insurance(account)

                self.natixis_life_ins_inv.go(account_path=account._natixis_url_path)
                if self.natixis_error.is_here():
                    raise BrowserUnavailable()

                if not self.page.has_history():
                    return []

                try:
                    self.natixis_life_ins_his.go(account_path=account._natixis_url_path)
                except BrowserHTTPError as e:
                    if e.response.status_code == 500:
                        error = json.loads(e.response.text)
                        raise BrowserUnavailable(error["error"])
                    raise
                return sorted_transactions(self.page.get_history())

            if account.label.startswith("NUANCES ") or account.label in self.insurance_accounts:
                # Some life insurances are not on the accounts summary
                self.home_tache.go(tache="EPASYNT0")
                self.page.go_life_insurance(account)
                # To access the life insurance space, we need to delete the JSESSIONID cookie
                # to avoid an expired session
                # There might be duplicated JSESSIONID cookies (eg with different paths),
                # that's why we need to use remove_cookie_by_name()
                remove_cookie_by_name(self.session.cookies, "JSESSIONID")

            if self.home.is_here():
                # no detail available for this account
                return []

            try:
                if not self.life_insurance.is_here() and not self.message.is_here():
                    # life insurance website is not always available
                    raise BrowserUnavailable()
                self.page.submit()
                self.life_insurance_history.go()
                # Life insurance transactions are not sorted by date in the JSON
                return sorted_transactions(self.page.iter_history())
            except ServerError as e:
                if e.response.status_code == 500:
                    raise BrowserUnavailable()
                raise

        return self.page.iter_history()

    @retry_on_logout()
    @need_login
    def iter_history(self, account):
        self.home.go()
        self.deleteCTX()

        if account.type == account.TYPE_CARD:

            def match_cb(tr):
                return self.card_matches(tr.card, account.number)

            hist = self._get_history(account.parent._info, account)
            hist = keep_only_card_transactions(hist, match_cb)
            return hist

        if not hasattr(account, "_info"):
            raise NotImplementedError
        if (
            account.type in (Account.TYPE_LIFE_INSURANCE, Account.TYPE_CAPITALISATION)
            and "measure_id" not in account._info
        ):
            return self._get_history_invests(account)
        if account.type in (Account.TYPE_MARKET, Account.TYPE_PEA):
            self.page.go_history(account._info)
            if "Bourse" in self.url:
                self.page.submit()
                if "offrebourse.com" in self.url:
                    # Some users may not have access to this.
                    if self.page.is_error():
                        return []

                    self.linebourse.session.cookies.update(self.session.cookies)
                    self.update_linebourse_token()
                    history = self.linebourse.iter_history(account.id)
                    # We need to go back to the synthesis, else we can not go home later
                    self.home_tache.go(tache="CPTSYNT0")
                    return history

        hist = self._get_history(account._info, False)
        return omit_deferred_transactions(hist)

    @retry_on_logout()
    @need_login
    def iter_coming(self, account):
        if account.type == account.TYPE_CHECKING:
            return self.get_coming_checking(account)
        elif account.type == account.TYPE_CARD:
            return self.get_coming_card(account)
        return []

    def get_coming_checking(self, account):
        # The accounts list or account history page does not contain comings for checking accounts
        # We need to go to a specific levies page where we can find past and coming levies (such as recurring ones)
        trs = []
        self.home.go()
        if "measure_id" in getattr(account, "_info", ""):
            self.go_measure_list(account._info["measure_id_page_num"])
            self.page.go_measure_accounts_list(account._info["measure_id"])
            self.page.go_history(account._info)

        self.page.go_cards()  # need to go to cards page to have access to the nav bar where we can choose LeviesPage from
        if not self.page.levies_page_enabled():
            return trs
        self.page.go_levies()  # need to go to a general page where we find levies for all accounts before requesting a specific account
        if not self.page.comings_enabled(account.id):
            return trs
        self.page.go_levies(account.id)
        if self.new_checkings_levies.is_here() or self.old_checkings_levies.is_here():
            today = datetime.today().date()
            # Today transactions are in this page but also in history page, we need to ignore it as a coming
            for tr in self.page.iter_coming():
                if tr.date > today:
                    trs.append(tr)
        return trs

    def get_coming_card(self, account):
        trs = []
        if not hasattr(account.parent, "_info"):
            raise NotImplementedError()
        # We are on the old website
        if hasattr(account, "_coming_eventargument"):
            if not self.cards_old.is_here():
                self.home.go()
                self.page.go_list()
                self.page.go_cards()
            self.page.go_card_coming(account._coming_eventargument)
            return sorted_transactions(self.page.iter_coming())
        # We are on the new website.
        info = account.parent._card_links
        # if info is empty, that means there are no comings yet
        if info:
            for tr in self._get_history(info.copy(), account):
                tr.type = tr.TYPE_DEFERRED_CARD
                trs.append(tr)
        return sorted_transactions(trs)

    @retry_on_logout()
    @need_login
    def iter_investments(self, account):
        self.deleteCTX()

        investable_types = (
            Account.TYPE_LIFE_INSURANCE,
            Account.TYPE_CAPITALISATION,
            Account.TYPE_MARKET,
            Account.TYPE_PEA,
        )
        if account.type not in investable_types or "measure_id" in account._info:
            raise NotImplementedError()

        if account.type == Account.TYPE_PEA and account.label == "PEA NUMERAIRE":
            yield create_french_liquidity(account.balance)
            return

        if self.home.is_here():
            self.page.go_list()
        else:
            self.home.go()

        if account.type in (Account.TYPE_MARKET, Account.TYPE_PEA):
            self.page.go_history(account._info)
            # Some users may not have access to this.
            if not self.market.is_here():
                return
            self.page.submit()

            if "offrebourse.com" in self.url:
                # Some users may not have access to this.
                if self.page.is_error():
                    return

                self.update_linebourse_token()
                yield from self.linebourse.iter_investments(account.id)

                # We need to go back to the synthesis, else we can not go home later
                self.home_tache.go(tache="CPTSYNT0")
                return

        elif account.type in (Account.TYPE_LIFE_INSURANCE, Account.TYPE_CAPITALISATION):
            if account._info["type"] == "SYNTHESE_EPARGNE":
                # If the type is not SYNTHESE_EPARGNE, it means we have a direct link and going
                # this way would set off a SyntaxError.
                self.page.go_history(account._info)

            if self.page.is_account_inactive(account.id):
                self.logger.warning(f"Account {account.label} {account.id} is inactive.")
                return
            if "MILLEVIE" in account.label:
                # This way we ensure we can access all type of MILLEVIE accounts
                self.home_tache.go(tache="EPASYNT0")
                self.page.go_life_insurance(account)
                self.natixis_life_ins_inv.go(account_path=account._natixis_url_path)
                if self.natixis_error.is_here():
                    raise BrowserUnavailable()
                yield from self.page.get_investments()
                return

            if not self.go_life_insurance_investments(account):
                return

        if self.garbage.is_here():
            self.page.come_back()
            return
        yield from self.page.iter_investment()
        if self.market.is_here():
            self.page.come_back()

    @need_login
    def go_life_insurance_investments(self, account):
        # Returns whether it managed to go to the page
        self.home_tache.go(tache="EPASYNT0")
        self.page.go_life_insurance(account)
        if self.home.is_here():
            # no detail is available for this account
            return False
        elif not self.market.is_here() and not self.message.is_here():
            # life insurance website is not always available
            raise BrowserUnavailable()
        self.page.submit()
        try:
            self.life_insurance_investments.go()
        except ServerError:
            raise BrowserUnavailable()
        return True

    @retry_on_logout()
    @need_login
    def iter_market_orders(self, account):
        if account.type not in (Account.TYPE_MARKET, Account.TYPE_PEA):
            return
        self.home.go()
        self.deleteCTX()
        self.page.go_history(account._info)
        if "Bourse" in self.url:
            self.page.submit()
            if "offrebourse.com" in self.url:
                # Some users may not have access to this.
                if self.page.is_error():
                    return
                self.linebourse.session.cookies.update(self.session.cookies)
                self.update_linebourse_token()
                try:
                    yield from self.linebourse.iter_market_orders(account.id)
                finally:
                    # We need to go back to the synthesis, else we can not go home later
                    self.home_tache.go(tache="CPTSYNT0")

    @retry_on_logout()
    @need_login
    def get_profile(self):
        profile = Profile()
        if len([k for k in self.session.cookies.keys() if k == "CTX"]) > 1:
            del self.session.cookies["CTX"]

        ctx = decode_utf8_cookie(self.session.cookies.get("CTX", ''))
        # str() to make sure a native str is used as expected by decode_utf8_cookie
        headerdei = decode_utf8_cookie(self.session.cookies.get("headerdei", ''))
        if "username=" in ctx:
            profile.name = re.search("username=([^&]+)", ctx).group(1)
        elif "nomusager=" in headerdei:
            profile.name = re.search("nomusager=(?:[^&]+/ )?([^&]+)", headerdei).group(1)
        return profile

    def card_matches(self, a, b):
        # For the same card, depending where we scrape it, we have
        # more or less visible number. `X` are visible number, `*` hidden one's.
        # tr.card: XXXX******XXXXXX, account.number: XXXXXX******XXXX
        return (a[:4], a[-4:]) == (b[:4], b[-4:])
