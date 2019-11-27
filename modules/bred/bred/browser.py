# Copyright(C) 2014 Romain Bignon
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

import json
import operator
import random
import time
from datetime import date, datetime
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from woob.browser import URL, need_login
from woob.browser.exceptions import ClientError
from woob.browser.mfa import TwoFactorBrowser
from woob.capabilities import NotAvailable
from woob.capabilities.bank import Account, AccountOwnerType, AddRecipientBankError, AddRecipientStep, TransferBankError
from woob.capabilities.base import find_object
from woob.exceptions import (
    ActionNeeded,
    AppValidation,
    AppValidationCancelled,
    AppValidationExpired,
    AuthMethodNotImplemented,
    BrowserIncorrectPassword,
    BrowserQuestion,
    BrowserUnavailable,
)
from woob.tools.capabilities.bank.investments import create_french_liquidity
from woob.tools.value import Value
from woob_modules.linebourse.browser import LinebourseAPIBrowser

from .pages import (
    AccountsPage,
    AccountsTwoFAPage,
    AuthentResultPage,
    CheckOtpPage,
    ErrorCodePage,
    ErrorMsgPage,
    ErrorPage,
    HomePage,
    IbanPage,
    InitAuthentPage,
    LifeInsurancesPage,
    LinebourseLoginPage,
    LoansPage,
    LoginPage,
    MandatesPage,
    MoveUniversePage,
    ProfilePage,
    SearchPage,
    SendSmsPage,
    StatementsPage,
    SwitchPage,
    TokenPage,
    TrustedDevicesPage,
    UnavailablePage,
    UniversePage,
)
from .transfer_pages import AddRecipientPage, EmittersListPage, ListAuthentPage, RecipientListPage, TransferPage


__all__ = ["BredBrowser"]


class BredBrowser(TwoFactorBrowser):
    BASEURL = "https://www.bred.fr"
    HAS_CREDENTIALS_ONLY = True

    LINEBOURSE_BROWSER = LinebourseAPIBrowser

    home = URL(r"/$", HomePage)
    login = URL(r"/transactionnel/Authentication", LoginPage)
    error = URL(
        r".*gestion-des-erreurs/erreur-pwd",
        r".*gestion-des-erreurs/opposition",
        r"/pages-gestion-des-erreurs/erreur-technique",
        r"/pages-gestion-des-erreurs/message-tiers-oppose",
        ErrorPage,
    )
    universe = URL(r"/transactionnel/services/applications/menu/getMenuUnivers", UniversePage)
    token = URL(r"/transactionnel/services/rest/User/nonce\?random=(?P<timestamp>.*)", TokenPage)
    move_universe = URL(r"/transactionnel/services/applications/listes/(?P<key>.*)/default", MoveUniversePage)
    switch = URL(r"/transactionnel/services/rest/User/switch", SwitchPage)
    loans = URL(r"/transactionnel/services/applications/prets/liste", LoansPage)
    accounts = URL(r"/transactionnel/services/rest/Account/accounts", AccountsPage)
    iban = URL(r"/transactionnel/services/rest/Account/account/(?P<number>.*)/iban", IbanPage)
    linebourse_login = URL(r"/transactionnel/v2/services/applications/SSO/linebourse", LinebourseLoginPage)
    life_insurances = URL(r"/transactionnel/services/applications/avoirsPrepar/getAvoirs", LifeInsurancesPage)
    search = URL(r"/transactionnel/services/applications/operations/getSearch/", SearchPage)
    profile = URL(r"/transactionnel/services/rest/User/user", ProfilePage)
    error_code = URL(r"/.*\?errorCode=.*", ErrorCodePage)
    error_msg_page = URL(r"/authentification\?source=no&errorCode=(?P<errorcode>\d)", ErrorMsgPage)
    unavailable_page = URL(r"/ERREUR/", UnavailablePage)
    mandates = URL(
        r"/transactionnel/services/applications/releves/comptes/mandates",
        r"/transactionnel/v2/services/applications/releves/comptes/mandates",
        MandatesPage,
    )
    statements = URL(
        r"/transactionnel/services/applications/releves/liste",
        r"/transactionnel/v2/services/applications/releves/liste",
        StatementsPage,
    )

    accounts_twofa = URL(r"/transactionnel/v2/services/rest/Account/accounts", AccountsTwoFAPage)
    list_authent = URL(
        r"/transactionnel/services/applications/authenticationstrong/listeAuthent/(?P<context>\w+)", ListAuthentPage
    )
    init_authent = URL(r"/transactionnel/services/applications/authenticationstrong/init", InitAuthentPage)
    authent_result = URL(
        r"/transactionnel/services/applications/authenticationstrong/result/(?P<authent_id>[^/]+)/(?P<context>\w+)",
        AuthentResultPage,
    )
    trusted_devices = URL(r"/transactionnel/services/applications/trustedDevices", TrustedDevicesPage)
    check_otp = URL(
        r"/transactionnel/services/applications/authenticationstrong/(?P<auth_method>\w+)/check", CheckOtpPage
    )
    send_sms = URL(r"/transactionnel/services/applications/authenticationstrong/sms/send", SendSmsPage)

    recipient_list = URL(r"/transactionnel/v2/services/applications/virement/getComptesCrediteurs", RecipientListPage)
    emitters_list = URL(r"/transactionnel/v2/services/applications/virement/getComptesDebiteurs", EmittersListPage)

    add_recipient = URL(r"/transactionnel/v2/services/applications/beneficiaires/updateBeneficiaire", AddRecipientPage)

    create_transfer = URL(r"/transactionnel/v2/services/applications/virement/confirmVirement", TransferPage)
    validate_transfer = URL(r"/transactionnel/v2/services/applications/virement/validVirement", TransferPage)

    __states__ = (
        "auth_method",
        "need_reload_state",
        "authent_id",
        "device_id",
        "context",
        "recipient_transfer_limit",
    )

    def __init__(self, accnum, config, *args, **kwargs):
        self.config = config
        kwargs["username"] = self.config["login"].get()

        # Bred only use first 8 char (even if the password is set to be bigger)
        # The js login form remove after 8th char. No comment.
        kwargs["password"] = self.config["password"].get()[:8]

        super().__init__(config, *args, **kwargs)

        self.accnum = accnum
        self.universes = None
        self.current_univers = None
        self.need_reload_state = None
        self.context = None
        self.device_id = None
        self.auth_method = None
        self.authent_id = None
        self.recipient_transfer_limit = None

        # Some accounts are detailed on linebourse. The only way to know which is to go on linebourse.
        # The parameters to do so depend on the universe.
        self.linebourse_urls = {}
        self.linebourse_tokens = {}
        dirname = self.responses_dirname
        if dirname:
            dirname += "/bourse"
        self.linebourse = self.LINEBOURSE_BROWSER(
            "https://www.linebourse.fr",
            logger=self.logger,
            responses_dirname=dirname,
            proxy=self.PROXIES,
        )

        self.AUTHENTICATION_METHODS = {
            "resume": self.handle_polling,  # validation in mobile app
            "otp_sms": self.handle_otp_sms,  # OTP in SMS
            "otp_app": self.handle_otp_app,  # OTP in mobile app
        }

    def load_state(self, state):
        # Is the browser being reloaded for 2FA?
        is_2fa = state.get("resume") or state.get("otp_sms") or state.get("otp_app")

        if state.get("need_reload_state") or state.get("device_id") or is_2fa:
            state.pop("url", None)
            super().load_state(state)
            self.need_reload_state = None

    def init_login(self):
        if self.device_id:
            # will not raise 2FA if the one realized with this id is still valid
            self.session.headers["x-trusted-device-id"] = self.device_id

        if "hsess" not in self.session.cookies:
            self.home.go()  # set session token
            assert "hsess" in self.session.cookies, "Session token not correctly set"

        # hard-coded authentication payload
        data = {
            "identifiant": self.username,
            "password": self.password,
        }
        self.login.go(data=data)

        if self.error_code.is_here():
            code = self.page.get_code()
            self.error_msg_page.go(errorcode=code)
            msg = self.page.get_msg()

            # 20100: invalid login/password
            if code == "20100":
                raise BrowserIncorrectPassword(msg)
            elif code == "20109":
                raise ActionNeeded(msg)
            # 20104 & 1000: unknown error during login
            elif code in ("20104", "1000"):
                raise BrowserUnavailable(msg)

            raise AssertionError("Error %s is not handled yet." % code)

        try:
            # It's an accounts page if SCA already done
            # Need to first go there to trigger it, since LoginPage doesn't do that.
            self.accounts_twofa.go()
        except ClientError as e:
            if e.response.status_code == 449:
                self.check_interactive()
                self.context = e.response.json()["content"]
                self.trigger_connection_twofa()
            raise

    def trigger_connection_twofa(self):
        # Needed to record the device doing the SCA and keep it valid.
        self.device_id = "".join([str(random.randint(0, 9)) for _ in range(50)])  # Python2 compatible
        # self.device_id = ''.join(random.choices(string.digits, k=50))  # better but needs Python3

        self.auth_method = self.get_connection_twofa_method()

        if self.auth_method == "notification":
            self.update_headers()
            data = {
                "context": self.context["contextAppli"],  # 'accounts_access'
                "type_auth": "NOTIFICATION",
                "type_phone": "P",
            }
            self.init_authent.go(json=data)
            self.authent_id = self.page.get_authent_id()
            if self.context.get("message"):
                raise AppValidation(self.context["message"])

            raise AppValidation("Veuillez valider l'accès sur votre application.")

        elif self.auth_method == "sms":
            self.update_headers()
            data = {
                "context": self.context["context"],
                "contextAppli": self.context["contextAppli"],
            }
            self.send_sms.go(json=data)

            if self.context.get("message"):
                raise BrowserQuestion(
                    Value("otp_sms", label=self.context["message"]),
                )

            raise BrowserQuestion(
                Value("otp_sms", label="Veuillez entrer le code reçu au %s" % self.context["liste"]["numTel"])
            )

        elif self.auth_method == "otp":
            if self.context.get("message"):
                raise BrowserQuestion(Value("otp_app", label=self.context["message"]))

            raise BrowserQuestion(
                Value("otp_app", label="Veuillez entrer le code reçu sur votre application."),
            )

    def get_connection_twofa_method(self):
        # The order and tests are taken from the bred website code.
        # Keywords in scripts.js: showSMS showEasyOTP showOTP
        methods = self.context["liste"]

        # Overriding default order of tests with 'preferred_sca' configuration item
        preferred_sca_value = self.config.get("preferred_sca")

        # Some children don't have this mechanism
        if preferred_sca_value:
            preferred_auth_methods = tuple(preferred_sca_value.get().split())
            for auth_method in preferred_auth_methods:
                if methods.get(auth_method):
                    return auth_method

        if methods.get("sms"):
            return "sms"
        elif methods.get("notification") and methods.get("otp"):
            return "notification"
        elif methods.get("otp"):
            return "otp"

        message = self.context["message"]
        raise AuthMethodNotImplemented("Unhandled strong authentification method: %s" % message)

    def update_headers(self):
        timestamp = int(time.time() * 1000)
        if self.device_id:
            self.session.headers["x-trusted-device-id"] = self.device_id
        self.token.go(timestamp=timestamp)
        self.session.headers["x-token-bred"] = self.page.get_content()

    def handle_polling(self, enrol=True):
        for _ in range(60):  # 5' timeout duration on website
            self.update_headers()
            self.authent_result.go(
                authent_id=self.authent_id,
                context=self.context["contextAppli"],
                json={},  # yes, needed
            )

            status = self.page.get_status()
            if not status:
                # When the notification expires, we get a generic error message
                # instead of a status like 'PENDING'
                self.context = None
                raise AppValidationExpired("La validation par application mobile a expiré.")

            elif status == "ABORTED":
                self.context = None
                raise AppValidationCancelled("La validation par application a été annulée par l'utilisateur.")

            elif status == "AUTHORISED":
                self.context = None
                if enrol:
                    self.enrol_device()
                return

            assert status == "PENDING", "Unhandled app validation status : '%s'" % status
            time.sleep(5)

        self.context = None
        raise AppValidationExpired("La validation par application mobile a expiré.")

    def handle_otp_sms(self):
        self.validate_connection_otp_auth(self.otp_sms)

    def handle_otp_app(self):
        self.validate_connection_otp_auth(self.otp_app)

    def validate_connection_otp_auth(self, auth_value):
        self.update_headers()
        data = {
            "context": self.context["context"],
            "contextAppli": self.context["contextAppli"],
            "otp": auth_value,
        }
        self.check_otp.go(
            auth_method=self.auth_method,
            json=data,
        )

        error = self.page.get_error()
        if error:
            raise BrowserIncorrectPassword("Error when validating OTP: %s" % error)

        self.context = None
        self.enrol_device()

    def enrol_device(self):
        # Add device_id to list of trusted devices to avoid SCA for 90 days
        # User will see a 'BI' entry on this list and can delete it on demand.
        self.update_headers()

        device_name = "Accès Budget-Insight pour agrégation"
        device_name_value = self.config.get("device_name")
        if device_name_value:
            device_name = device_name_value.get()

        data = {
            "uuid": self.device_id,  # Called an uuid but it's just a 50 digits long string.
            "deviceName": device_name,  # clear message for user
            "biometricEnabled": False,
            "securedBiometricEnabled": False,
            "notificationEnabled": False,
        }
        self.trusted_devices.go(json=data)

        error = self.page.get_error()
        if error:
            raise BrowserIncorrectPassword("Error when enroling trusted device: %s" % error)

    @need_login
    def get_universes(self):
        """Get universes (particulier, pro, etc)"""
        self.update_headers()
        self.universe.go(headers={"Accept": "application/json"})

        return self.page.get_universes()

    def move_to_universe(self, univers):
        if univers == self.current_univers:
            return
        self.move_universe.go(key=univers)
        self.update_headers()
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        self.switch.go(
            data=json.dumps({"all": "false", "univers": univers}),
            headers=headers,
        )
        self.current_univers = univers

    def linebourse_login_for_universe(self, universe):
        self.linebourse_login.go()
        if self.linebourse_login.is_here():
            linebourse_url = self.page.get_linebourse_url()
            if linebourse_url:
                self.linebourse_urls[universe] = linebourse_url
                self.linebourse_tokens[universe] = self.page.get_linebourse_token()

    def universe_to_owner_type(self, universe_key):
        # P particulire
        # M immobilier
        # E entreprise
        # R pro
        # S pro+
        if universe_key in ["P", "M"]:
            return AccountOwnerType.PRIVATE
        elif universe_key in ["E", "R", "S"]:
            return AccountOwnerType.ORGANIZATION
        else:
            self.logger.error("New universe to convert to owner_type: %s", universe_key)
            return NotAvailable

    @need_login
    def get_accounts_list(self):
        accounts = []
        for universe_key in sorted(self.get_universes()):
            self.move_to_universe(universe_key)
            universe_accounts = []
            owner_type = self.universe_to_owner_type(universe_key)
            universe_accounts.extend(self.get_list())
            universe_accounts.extend(self.get_life_insurance_list())
            universe_accounts.extend(self.get_loans_list())
            linebourse_accounts = self.get_linebourse_accounts(universe_key)

            for account in universe_accounts:
                account._is_in_linebourse = False
                account.owner_type = owner_type
                # Accound id looks like 'bred_account_id.folder_id'
                # We only want bred_account_id and we need to clean it to match it to linebourse IDs.
                account_id = account.id.strip("0").split(".")[0]
                for linebourse_account in linebourse_accounts:
                    if account_id in linebourse_account:
                        account._is_in_linebourse = True
            accounts.extend(universe_accounts)

        # Life insurances are sometimes in multiple universes, we have to remove duplicates
        unique_accounts = {account.id: account for account in accounts}.values()

        # Fill parents with resulting accounts when relevant:
        for account in unique_accounts:
            if account.type not in [Account.TYPE_CARD, Account.TYPE_LIFE_INSURANCE]:
                continue
            account.parent = find_object(unique_accounts, _number=account._parent_number, type=Account.TYPE_CHECKING)

        return sorted(unique_accounts, key=operator.attrgetter("_univers"))

    @need_login
    def get_linebourse_accounts(self, universe_key):
        self.move_to_universe(universe_key)
        if universe_key not in self.linebourse_urls:
            self.linebourse_login_for_universe(universe_key)
        if universe_key in self.linebourse_urls:
            self.linebourse.location(
                self.linebourse_urls[universe_key], data={"SJRToken": self.linebourse_tokens[universe_key]}
            )
            self.linebourse.session.headers["X-XSRF-TOKEN"] = self.linebourse.session.cookies.get("XSRF-TOKEN")
            params = {"_": f"{int(time.time() * 1000)}"}
            try:
                self.linebourse.go_account_codes(params=params)
            except self.LINEBOURSE_BROWSER.LinebourseNoSpace:
                return []
            if self.linebourse.account_codes.is_here():
                return self.linebourse.page.get_accounts_list()
        return []

    @need_login
    def get_loans_list(self):
        self.loans.go()
        return self.page.iter_loans(current_univers=self.current_univers)

    @need_login
    def get_list(self):
        self.accounts.go()
        return self.page.iter_accounts(accnum=self.accnum, current_univers=self.current_univers)

    @need_login
    def get_life_insurance_list(self):
        self.life_insurances.go()
        self.page.check_error()
        return self.page.iter_lifeinsurances(univers=self.current_univers)

    @need_login
    def _make_api_call(self, account, start_date, end_date, offset, max_length=50):
        self.update_headers()
        call_payload = {
            "account": account._number,
            "poste": account._nature,
            "sousPoste": account._codeSousPoste or "00",
            "devise": account.currency,
            "fromDate": start_date.strftime("%Y-%m-%d"),
            "toDate": end_date.strftime("%Y-%m-%d"),
            "from": offset,
            "size": max_length,  # max length of transactions
            "search": "",
            "categorie": "",
        }
        result = self.search.go(json=call_payload)
        self.page.check_error()
        return result

    @need_login
    def iter_history(self, account, coming=False):
        if account.type in (Account.TYPE_LOAN, Account.TYPE_LIFE_INSURANCE) or not account._consultable:
            raise NotImplementedError()

        self.move_to_universe(account._univers)

        today = date.today()
        end_date = date.today()
        start_date = date(day=1, month=1, year=2000)
        max_length = 50
        successive_hist_transaction_counter = 0

        self._make_api_call(
            account=account,
            start_date=start_date,
            end_date=end_date,
            offset=0,
            max_length=max_length,
        )

        max_transactions = self.page.get_max_transactions()

        for transaction in self.page.iter_history(
            account=account,
            account_type=account.type,
            today=today,
            start_date=start_date,
            end_date=end_date,
            max_length=max_length,
            max_transactions=max_transactions,
        ):
            if coming == transaction.coming:
                successive_hist_transaction_counter = 0

                yield transaction

            elif coming and not transaction.coming:
                # coming transactions are at the top of history, but we make sure that there
                # are no transactions in coming after few transactions that are not in coming.
                # If we encounter more than 10 successive history transactions, we stop the iteration.
                successive_hist_transaction_counter += 1
                if successive_hist_transaction_counter > 10:
                    self.logger.debug("stopping coming after %s", transaction)
                    return

    @need_login
    def iter_investments(self, account):
        if account.type == Account.TYPE_LIFE_INSURANCE:
            yield from account._investments

        elif account.type in (Account.TYPE_PEA, Account.TYPE_MARKET):
            if "Portefeuille Titres" in account.label:
                if account._is_in_linebourse:
                    self.move_to_universe(account._univers)
                    self.linebourse_login_for_universe(account._univers)
                    self.linebourse.location(
                        self.linebourse_urls[account._univers],
                        data={"SJRToken": self.linebourse_tokens[account._univers]},
                    )
                    self.linebourse.session.headers["X-XSRF-TOKEN"] = self.linebourse.session.cookies.get("XSRF-TOKEN")
                    yield from self.linebourse.iter_investments(account.id.strip("0").split(".")[0])
                else:
                    raise NotImplementedError()
            else:
                # Compte espèces
                yield create_french_liquidity(account.balance)

        else:
            raise NotImplementedError()

    @need_login
    def iter_market_orders(self, account):
        if account.type not in (Account.TYPE_MARKET, Account.TYPE_PEA):
            return

        if "Portefeuille Titres" in account.label:
            if account._is_in_linebourse:
                self.move_to_universe(account._univers)
                self.linebourse_login_for_universe(account._univers)
                self.linebourse.location(
                    self.linebourse_urls[account._univers], data={"SJRToken": self.linebourse_tokens[account._univers]}
                )
                self.linebourse.session.headers["X-XSRF-TOKEN"] = self.linebourse.session.cookies.get("XSRF-TOKEN")
                yield from self.linebourse.iter_market_orders(account.id.strip("0").split(".")[0])

    @need_login
    def get_profile(self):
        self.get_universes()

        self.profile.go()
        return self.page.get_profile()

    @need_login
    def fill_account(self, account, fields):
        if account.type == Account.TYPE_CHECKING and "iban" in fields:
            self.iban.go(number=account._number)
            self.page.set_iban(account=account)

    @need_login
    def iter_transfer_recipients(self, account):
        self.move_to_universe(account._univers)
        self.update_headers()
        try:
            self.emitters_list.go(
                json={
                    "typeVirement": "C",
                }
            )
        except ClientError as e:
            if e.response.status_code == 403:
                msg = e.response.json().get("erreur", {}).get("libelle", "")
                if msg == "Cette fonctionnalité n'est pas disponible avec votre compte.":
                    # Means the account cannot emit transfers
                    return
            raise

        if not self.page.can_account_emit_transfer(account.id):
            return

        self.update_headers()
        account_id = account.id.split(".")[0]
        self.recipient_list.go(
            json={
                "numeroCompteDebiteur": account_id,
                "typeVirement": "C",
            }
        )

        for obj in self.page.iter_external_recipients():
            yield obj

        for obj in self.page.iter_internal_recipients():
            if obj.id != account.id:
                yield obj

    def do_strong_authent_recipient(self, recipient):
        self.list_authent.go(context=self.context["contextAppli"])
        self.auth_method = self.page.get_handled_auth_methods()

        if not self.auth_method:
            raise AuthMethodNotImplemented()

        self.need_reload_state = self.auth_method != "password"

        if self.auth_method == "password":
            return self.validate_strong_authent_recipient(self.password)
        elif self.auth_method == "otp":
            raise AddRecipientStep(
                recipient,
                Value(
                    "otp",
                    label="Veuillez générez un e-Code sur votre application BRED puis saisir cet e-Code ici",
                ),
            )
        elif self.auth_method == "notification":
            self.update_headers()
            self.init_authent.go(
                json={
                    "context": self.context["contextAppli"],
                    "type_auth": "NOTIFICATION",
                    "type_phone": "P",
                }
            )
            self.authent_id = self.page.get_authent_id()
            raise AppValidation(
                resource=recipient,
                message="Veuillez valider la notification sur votre application mobile BRED",
            )
        elif self.auth_method == "sms":
            self.update_headers()
            self.send_sms.go(
                json={
                    "contextAppli": self.context["contextAppli"],
                    "context": self.context["context"],
                }
            )
            raise AddRecipientStep(
                recipient,
                Value("code", label="Veuillez saisir le code reçu par SMS"),
            )

    def validate_strong_authent_recipient(self, auth_value):
        self.update_headers()
        self.check_otp.go(
            auth_method=self.auth_method,
            json={
                "contextAppli": self.context["contextAppli"],
                "context": self.context["context"],
                "otp": auth_value,
            },
        )

        error = self.page.get_error()
        if error:
            raise AddRecipientBankError(message=error)

    def new_recipient(self, recipient, **params):
        if "otp" in params:
            self.validate_strong_authent_recipient(params["otp"])
        elif "code" in params:
            self.validate_strong_authent_recipient(params["code"])
        elif "resume" in params:
            self.handle_polling(enrol=False)

        return self.init_new_recipient(recipient, **params)

    @need_login
    def init_new_recipient(self, recipient, **params):
        for _ in range(3):
            # The goal of this is to find the maximum allowed, by Bred,
            # limit for transfers on new recipient. For this we do a request
            # with an absurdly high limit , and the error message will tell us
            # what is that maximum allowed limit by the bank.
            #
            # 5000€ is the default value for the recipient transfer limit
            # on BRED Connect.
            # TODO: What if the transfer limit is more than 5000€?
            json_data = {
                "nom": recipient.label,
                "iban": recipient.iban,
                "numCompte": "",
                "plafond": str(int(self.recipient_transfer_limit or 5000)),
                "typeDemande": "A",
            }

            try:
                self.update_headers()
                self.add_recipient.go(json=json_data)
            except ClientError as e:
                if e.response.status_code != 449:
                    # Status code 449 means we need to do strong authentication
                    raise

                self.context = e.response.json()["content"]
                self.do_strong_authent_recipient(recipient)

                # Password authentication do not raise error, so we need
                # to re-execute the request here.
                if self.auth_method == "password":
                    self.update_headers()
                    self.add_recipient.go(json=json_data)

            # If the error we encounter here lists a transfer limit, we use
            # this as the new recipient transfer limit for the account.
            # Otherwise, it means that our current transfer limit has been
            # accepted and either the recipient has been added successfully,
            # or that another error has occurred.
            recipient_transfer_limit = self.page.get_transfer_limit()
            if recipient_transfer_limit:
                self.recipient_transfer_limit = recipient_transfer_limit
                continue

            break
        else:
            raise AssertionError(
                "Could not find the recipient transfer limit!",
            )

        error_code = self.page.get_error_code()
        # '3200' is a warning, but the recipient has been added successfully.
        if error_code != "3200":
            error = self.page.get_error()
            if error:
                raise AddRecipientBankError(message=error)

        return recipient

    @need_login
    def init_transfer(self, transfer, account, recipient, **params):
        self.move_to_universe(account._univers)

        account_id = account.id.split(".")[0]
        poste = account.id.split(".")[1]

        amount = transfer.amount.quantize(Decimal(10) ** -2)
        if not amount % 1:
            # Number is an integer without floating numbers.
            # We need to not display the floating points in the request
            # if the number is an integer or the request will not work.
            amount = int(amount)

        json_data = {
            "compteDebite": account_id,
            "posteDebite": poste,
            "deviseDebite": account.currency,
            "deviseCredite": recipient.currency,
            "dateEcheance": transfer.exec_date.strftime("%d/%m/%Y"),
            "montant": str(amount),
            "motif": transfer.label,
            "virementListe": True,
            "plafondBeneficiaire": "",
            "nomBeneficiaire": recipient.label,
            "checkBeneficiaire": False,
            "instantPayment": False,
        }

        if recipient.category == "Interne":
            recipient_id_split = recipient.id.split(".")
            json_data["compteCredite"] = recipient_id_split[0]
            json_data["posteCredite"] = recipient_id_split[1]
        else:
            json_data["iban"] = recipient.iban

        self.update_headers()
        self.create_transfer.go(json=json_data)

        error = self.page.get_error()
        if error:
            raise TransferBankError(message=error)

        transfer.amount = self.page.get_transfer_amount()
        transfer.currency = self.page.get_transfer_currency()

        # The same data is needed to validate the transfer.
        transfer._json_data = json_data
        return transfer

    @need_login
    def execute_transfer(self, transfer, **params):
        self.update_headers()
        # This sends an email to the user to tell him that a transfer
        # has been created.
        self.validate_transfer.go(json=transfer._json_data)

        error = self.page.get_error()
        if error:
            raise TransferBankError(message=error)

        return transfer

    @need_login
    def iter_subscription(self):
        self.mandates.go()
        subscriptions_list = list(self.page.iter_subscription())
        yield from subscriptions_list

    @need_login
    def iter_documents(self, subscription):
        yield from self._iter_statements(subscription)

    def _fetch_statement_list(self, idPM, numeroCompte, dateFrom, dateTo):
        body = {
            "idPM": idPM,
            "numeroCompte": numeroCompte,
            "dateTo": dateTo.strftime("%d/%m/%Y"),
            "dateFrom": dateFrom.strftime("%d/%m/%Y"),
        }

        _saved_session_headers = self.session.headers
        self.session.headers = {"Content-Type": "application/json", "Accept": "application/json"}
        self.update_headers()
        self.statements.go(
            data=json.dumps(body),
        )
        self.session.headers = _saved_session_headers

    def _iter_statements(self, subscription):

        idPM = subscription._idPM
        numeroCompte = subscription.id

        end_date = datetime.today()
        start_date = end_date + relativedelta(years=-1)
        while True:
            self._fetch_statement_list(idPM, numeroCompte, start_date, end_date)

            has_data = False
            for d in self.page.iter_documents(subscription):
                has_data = True
                yield d

            if not has_data:
                break

            end_date = start_date
            start_date = start_date + relativedelta(years=-1)
