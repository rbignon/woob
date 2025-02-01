# Copyright(C) 2018-2023 Powens
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

import json
import random
from copy import copy
from datetime import date, datetime, time, timedelta

from dateutil.tz import tzutc
from urllib3.filepost import encode_multipart_formdata

from woob.browser import URL, need_login
from woob.browser.exceptions import ClientError
from woob.browser.mfa import TwoFactorBrowser
from woob.capabilities.bank import Account
from woob.capabilities.bank.transfer import (
    AddRecipientBankError,
    AddRecipientStep,
    TransferBankError,
    TransferDateType,
    TransferNotFound,
)
from woob.capabilities.base import empty
from woob.exceptions import (
    AppValidationExpired,
    BrowserIncorrectPassword,
    DecoupledMedium,
    DecoupledValidation,
    RecaptchaV2Question,
    WrongCaptchaResponse,
)
from woob.tools.date import now_as_utc
from woob.tools.json import WoobEncoder
from woob.tools.misc import polling_loop
from woob.tools.value import ValueBool

from .pages import (
    AccountsPage,
    AuthenticateCheckPage,
    AuthenticatePage,
    AuthenticateStatusPage,
    CreateRecipientPage,
    ErrorPage,
    HomePage,
    LoginPage,
    OperationsPage,
    ProfilePage,
    PublicPropertiesPage,
    RecipientsPage,
    TransferDebitAccountsPage,
    TransferExecutePage,
    TransferHistoryPage,
    TransferOngoingPage,
    TransferPage,
    TransferValidateCumulativePage,
    TransferValidatePage,
    TransferValidateUnitPage,
    VerifyRecipientCreatedPage,
)


class OrangeBankBrowser(TwoFactorBrowser):
    BASEURL = "https://www.orangebank.fr/"

    login = URL(r"espace-client/authentication/", LoginPage)
    home = URL(r"espace-client/home/", HomePage)

    authenticate = URL(
        r"portalserver/services/oslo-authentication/authenticate/public/customer/authenticate-login-context",
        AuthenticatePage,
    )
    authenticate_status = URL(
        r"portalserver/services/oslo-authentication/authenticate/public/customer/authentication-status",
        AuthenticateStatusPage,
    )

    customer = URL(
        r"portalserver/services/oslo-services/customer$",
        ProfilePage,
    )
    accounts = URL(
        r"portalserver/services/oslo-services/customer/accounts$",
        AccountsPage,
    )
    operations = URL(
        r"portalserver/services/oslo-services/customer/accounts/v2/(?P<equipmentId>.*)/operations/all",
        OperationsPage,
    )
    create_recipient = URL(
        r"portalserver/services/oslo-services/customer/beneficiaries/creation-request/v2",
        CreateRecipientPage,
    )
    verify_recipient_created = URL(
        r"portalserver/services/oslo-services/customer/beneficiaries/iban/completed/v2",
        VerifyRecipientCreatedPage,
    )
    authenticate_check = URL(
        r"portalserver/services/oslo-services/customer/customization/check-status",
        AuthenticateCheckPage,
    )
    recipients = URL(
        r"portalserver/services/oslo-services/customer/transfers/resources/v2",
        RecipientsPage,
    )
    transfer_debit_accounts = URL(
        r"portalserver/services/oslo-services/customer/transfers/find-debit-accounts-for-transfer/v2",
        TransferDebitAccountsPage,
    )
    transfer_validate = URL(
        r"portalserver/services/oslo-services/customer/transfers/verify/v2",
        TransferValidatePage,
    )
    transfer_validate_unit = URL(
        r"portalserver/services/oslo-services/customer/transfers/verify/amount/unit/beneficiary/(?P<beneficiary_id>[^/]{6,})/v2",
        TransferValidateUnitPage,
    )
    transfer_validate_cumulative = URL(
        r"portalserver/services/oslo-services/customer/transfers/verify/amount/cumulative/beneficiary/(?P<beneficiary_id>[^/]{6,})/v2",
        TransferValidateCumulativePage,
    )
    transfer_execute = URL(
        r"portalserver/services/oslo-services/customer/transfers/execute/v2",
        TransferExecutePage,
    )
    transfer_ongoing = URL(
        r"portalserver/services/oslo-services/customer/transfers/ongoing/v2",
        TransferOngoingPage,
    )
    transfer_history = URL(
        r"portalserver/services/oslo-services/customer/transfers/history/v2",
        TransferHistoryPage,
    )
    transfer = URL(
        r"portalserver/services/oslo-services/customer/transfers/(?P<transfer_id>[^/]{10,})/v2",
        TransferPage,
    )
    public_properties = URL(
        r"portalserver/services/oslo-services/public/public-properties",
        PublicPropertiesPage,
    )

    def __init__(self, config, *args, **kwargs):
        super().__init__(config, config["login"].get(), None, *args, **kwargs)

        self.AUTHENTICATION_METHODS = {
            "captcha_response": self.handle_captcha,
            "resume": self.handle_polling,
        }

        self.__states__ += ("polling_id", "inwebo_session_id")
        self.polling_id = None
        self.inwebo_session_id = None  # For beneficiaries.

    def build_request(self, *args, **kwargs):
        request = super().build_request(*args, **kwargs)

        # Add CSRF protection to be sent as a header.
        bbxsrf_token = self.session.cookies.get("BBXSRF")
        if bbxsrf_token:
            request.headers["x-bbxsrf"] = bbxsrf_token

        return request

    def locate_browser(self, state):
        super().locate_browser(state)
        if not self.home.is_here():
            return

        # Home page might still work when logged in, but we need to check
        # if a call to the accounts returns a 403; if that's the case,
        # we want to go back to the login page.
        try:
            self.accounts.open()
        except ClientError as exc:
            if exc.response.status_code != 403:
                raise

            self.login.go()

    def init_login(self):
        self.login.stay_or_go()

        # Obtain the BBXSRF cookie.
        page = self.public_properties.open()
        website_key = page.get_captcha_key()

        raise RecaptchaV2Question(
            website_key=website_key,
            website_url=self.page.url,
        )

    def handle_captcha(self):
        try:
            page = self.authenticate.open(
                json={
                    "additionalParameter": "WEB",
                    "captchaView": {"token": self.captcha_response},
                    "login": self.username,
                }
            )
        except ClientError as exc:
            try:
                error_page = ErrorPage(self, exc.response)
                error = error_page.get_error()
                message = error_page.get_error_message() or "."
            except KeyError:
                pass
            else:
                if error == "CUSTOMER_NOT_FOUND":
                    raise BrowserIncorrectPassword(
                        "Cet identifiant est inconnu dans notre système.",
                    )
                elif error == "CAPTCHA_TOKEN_ERROR":
                    raise WrongCaptchaResponse()

                if message != ".":
                    message = ": " + message

                raise AssertionError(f"Unknown error {error}{message}")

        # Decoupled validation is systematically raised.
        self.polling_id = page.get_polling_id()

        raise DecoupledValidation(
            message=("Nous vous invitons à autoriser la connexion depuis " + "votre mobile."),
            medium_type=DecoupledMedium.MOBILE_APP,
            expires_at=now_as_utc() + timedelta(minutes=1),
        )

    def handle_polling(self):
        # TwoFactorBrowser does not clear SCA keys in the case of
        # AppValidationError exceptions, so we want to clear the 'resume'
        # config key here so that if the polling fails, init_login is
        # called again.
        value = copy(self.config["resume"])
        value.set(value.default)
        self.config["resume"] = value

        for _ in polling_loop(count=40, delay=5):
            data = {
                "login": self.username,
                "additionalParameter": self.polling_id,
            }

            try:
                page = self.authenticate_status.open(
                    headers={"bodyParameters": json.dumps(data)},
                    json=data,
                )
            except ClientError as exc:
                # The WAITING_AUTHENTICATION and AUTHENTICATION_TIMEOUT
                # statuses are returned with an HTTP 412 status.
                if exc.response.status_code != 412:
                    raise

                page = AuthenticateStatusPage(self, exc.response)
                status = page.get_polling_status()
                if status is None:
                    # Not an actual authenticate status page.
                    raise
            else:
                # For HTTP 2xx statuses, we expect a polling status!
                status = page.get_polling_status()

            if status == "WAITING_AUTHENTICATION":
                continue
            elif status in ("AUTHENTICATION_TIMEOUT", "AUTHENTICATION_FAIL"):
                # AUTHENTICATION_TIMEOUT is raised directly, whereas
                # AUTHENTICATION_FAIL is raised in the same scenario if
                # the endpoint is queried later (e.g. if polling with the
                # same identifier is resumed after getting an
                # AUTHENTICATION_TIMEOUT status).
                #
                # Note that it is not possible to cancel the access request
                # from the mobile application in this scenario, since the
                # mobile application closes as soon as the PSU has entered
                # their password.
                #
                # The message on the website is generic, i.e.
                # "Désolé ! Nous n'avons pas pu vous authentifier."
                # We want to be more explicit.
                raise AppValidationExpired(
                    "Vous n'avez pas validé l'accès sur l'application " + "mobile dans les temps.",
                )
            elif status == "AUTHENTICATED":
                break

            raise AssertionError(f"Unhandled polling status {status!r}.")
        else:
            self.logger.warning(
                "Still waiting authentication after 40 attempts; " + "did the decoupled validity duration get longer?",
            )
            raise AppValidationExpired(
                "Vous n'avez pas validé l'accès sur l'application " + "mobile dans les temps.",
            )

        page = self.authenticate_check.open()
        next_step = page.get_next_step()

        if next_step != "ALL_DONE":
            raise AssertionError(f"Unknown nextStep {next_step!r}.")

        # Go to a logged page.
        self.home.go()

    @need_login
    def iter_accounts(self):
        page = self.accounts.open()
        return page.iter_accounts()

    @need_login
    def iter_history(self, account):
        return self.operations.open(
            equipmentId=account._equipmentId,
        ).iter_operations()

    @need_login
    def get_profile(self):
        return self.customer.open().get_profile()

    @need_login
    def iter_transfer_recipients(self, account):
        account_number = account
        if isinstance(account_number, Account):
            account_number = account_number.number

        page = self.recipients.open()
        return page.iter_transfer_recipients(account_number=account_number)

    @need_login
    def init_transfer(self, transfer, **params):
        if empty(transfer.currency):
            transfer.currency = "EUR"
        elif transfer.currency != "EUR":
            raise TransferBankError("Transfer currency must be EUR.")

        # Get the transfer date.
        transfer_date = transfer.exec_date or datetime.utcnow()
        if isinstance(transfer_date, date) and not isinstance(transfer_date, datetime):
            if empty(transfer.date_type) or transfer.date_type == TransferDateType.FIRST_OPEN_DAY:
                # We need a current UTC datetime here, we'll take the
                # current time.
                transfer_date = datetime.utcnow()
            else:
                transfer_date = datetime.combine(transfer_date, time(0, 0, 0))
        elif transfer_date.tzinfo:
            # We need to have a UTC datetime here.
            transfer_date = transfer_date.astimezone(tzutc()).replace(tzinfo=None)

        # Find the recipient account.
        page = self.recipients.open()
        transfer._beneficiaryId = page.get_recipient_id(
            transfer.recipient_iban or transfer.recipient_id,
        )

        if transfer._beneficiaryId is None:
            raise AssertionError("Could not find recipient for IBAN.")

        transfer.exec_date = transfer_date

        # Validate the transferred amounts as a unit.
        try:
            response = self.open(
                self.transfer_validate_unit.build(
                    beneficiary_id=transfer._beneficiaryId,
                ),
                json={"amount": transfer.amount},
            )
        except ClientError as exc:
            error_page = ErrorPage(self, exc.response)
            error = error_page.get_error()
            message = error_page.get_error_message()

            # This error is returned with an HTTP 412 status code.
            # It does not block the transfer, so we only emit a warning here.
            if error == "EXTERNAL_UNIT_AMOUNT_EXCEEDED":
                self.logger.warning(message)
            else:
                raise
        else:
            if response.status_code != 204:
                raise AssertionError(
                    "Expected an HTTP 204 on transfer validate unit.",
                )

        # We need to get the equipment identifier for the source account.
        page = self.transfer_debit_accounts.open(
            params={
                "amount": transfer.amount,
                "type": "IMMEDIATE",
            }
        )

        transfer._sourceEquipmentId = page.get_account_id(transfer.account_id)
        if not transfer._sourceEquipmentId:
            raise AssertionError(
                "No source equipment identifier for the given account.",
            )

        # Validate the transfer as a whole.
        transfer_date = transfer.exec_date.isoformat(timespec="milliseconds") + "Z"

        page = self.transfer_validate.open(
            json={
                "amount": transfer.amount,
                "deadlineDate": transfer_date,
                "sourceAccountEquipmentId": transfer._sourceEquipmentId,
                "transferBeneficiaryId": transfer._beneficiaryId,
                "transferType": "IMMEDIATE",
            }
        )

        status = page.get_transfer_status()
        if status != "VALIDATED":
            raise AssertionError(
                f"Unknown transfer validation status {status!r}.",
            )

        # Validate the transferred amounts cumulatively.
        response = self.open(
            self.transfer_validate_cumulative.build(
                beneficiary_id=transfer._beneficiaryId,
            ),
            json={
                "amount": transfer.amount,
                "deadLineDate": transfer_date,
                "sourceAccountId": transfer._sourceEquipmentId,
            },
        )

        if response.status_code != 204:
            raise AssertionError(
                "Expected a 204 on transfer validate cumulative.",
            )

        return transfer

    @need_login
    def execute_transfer(self, transfer, **params):
        transfer_date = transfer.exec_date.isoformat(timespec="milliseconds") + "Z"

        transfer_data = {
            "amount": transfer.amount,
            "sourceAccountEquipmentId": transfer._sourceEquipmentId,
            # 'periodicity': None,
            "deadlineDate": transfer_date,
            # 'endDate': None,
            "motive": transfer.label or "",
            "transferType": "IMMEDIATE",
            "transferBeneficiaryId": transfer._beneficiaryId,
        }

        # The boundary must be set here with a specific format, and not to a
        # boundary as set by requests, otherwise we are only greeted with
        # an HTTP 403 with no error message.
        data, content_type = encode_multipart_formdata(
            fields={
                "typedTransferDataView": (
                    "blob",
                    json.dumps(
                        transfer_data,
                        cls=WoobEncoder,
                        separators=(",", ":"),
                    ).encode("utf-8"),
                    "application/json",
                ),
            },
            boundary="-" * 27 + "".join(random.choice("0123456789") for _ in range(29)),
        )

        page = self.transfer_execute.open(
            headers={"Content-Type": content_type},
            data=data,
        )

        status = page.get_transfer_status()
        if status != "ACCEPTED":
            raise AssertionError(
                f"Unknown transfer execution status {status!r}.",
            )

        # We actually need to go all the way into the historic views to find
        # the id of our transfer, and where our transfer is at.
        #
        # NOTE: This also mainly works because transfers in the transfer
        #       lists are ordered by descending execution date.
        for url in (self.transfer_ongoing, self.transfer_history):
            page = url.open()
            for other_transfer in page.iter_transfers():
                if (
                    other_transfer.amount != transfer.amount
                    or other_transfer.currency != transfer.currency
                    or other_transfer.label != transfer.label
                ):
                    continue

                # Check if created today.
                other_date = other_transfer.creation_date
                if isinstance(other_date, datetime):
                    other_date = other_date.date()

                if not empty(other_date) and other_date != datetime.utcnow().date():
                    continue

                # We should have the right transfer.
                page = self.transfer.open(transfer_id=other_transfer._id)
                return page.get_transfer(obj=other_transfer)

        raise AssertionError(
            "We could not find the executed transfer in the available lists.",
        )

    @need_login
    def get_transfer(self, transfer_id):
        for url in (self.transfer_ongoing, self.transfer_history):
            page = url.open()
            for other_transfer in page.iter_transfers():
                if other_transfer.id != transfer_id:
                    continue

                page = self.transfer.open(transfer_id=other_transfer._id)
                return page.get_tranfer(obj=other_transfer)

        raise TransferNotFound()

    @need_login
    def new_recipient(self, recipient, **params):
        if self.inwebo_session_id and params.get("resume", False):
            return self.new_recipient_handle_polling(recipient)

        try:
            page = self.create_recipient.open(
                json={
                    "holderName": recipient.label,
                    "name": recipient.label,
                    "nickName": recipient.label,
                    "iban": recipient.iban,
                    "myAccount": False,
                }
            )
        except ClientError as exc:
            page = ErrorPage(self, exc.response)
            raise AddRecipientBankError(page.get_error_message())

        self.inwebo_session_id = page.get_inwebo_session_id()
        recipient.id = page.get_beneficiary_id()

        # TODO: Find out the message that is presented to the end user
        #       in this case.
        raise AddRecipientStep(
            recipient,
            ValueBool("resume", label="Veuillez valider dans l'application."),
        )

    def new_recipient_handle_polling(self, recipient):
        # Poll the status of the 'inwebo' authentication, i.e. the app
        # validation.
        for _ in polling_loop(count=40, delay=5):
            try:
                self.verify_recipient_created.open(
                    json={
                        "inweboSessionId": self.inwebo_session_id,
                        "transferBeneficiaryId": recipient.id,
                    }
                )
            except ClientError as exc:
                page = ErrorPage(self, exc.response)
                error = page.get_error()

                if error == "TRANSFER_BENEFICIARY_WAITING_FOR_INWEBO_AUTHENTICATION":
                    continue

                # TODO: Find out what errors are done by denying the request
                #       on the application.
                raise AddRecipientBankError(page.get_error_message())

            # We have received a 2xx status code, which means that
            # our recipient has successfully been created!
            break
        else:
            self.logger.warning(
                "Still waiting authentication for creating a recipient "
                + "after 40 attempts; did the decoupled validity duration "
                + "get longer?",
            )
            raise AddRecipientBankError(
                "Vous n'avez pas validé la création du bénéficiaire sur " + "l'application mobile dans les temps.",
            )

        # We do not need to get the beneficiary status from here as it will
        # be updated when calling iter_transfer_recipients.
        self.inwebo_session_id = None
        return recipient
