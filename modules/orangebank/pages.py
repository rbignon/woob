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

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    CleanDecimal,
    CleanText,
    Coalesce,
    Currency,
    Date,
    DateTime,
    Env,
    Field,
    Format,
    Map,
)
from woob.browser.pages import JsonPage, LoggedPage, RawPage
from woob.capabilities.bank import Account
from woob.capabilities.bank.transfer import Recipient, Transfer, TransferDateType, TransferStatus
from woob.capabilities.base import NotAvailable
from woob.capabilities.profile import Person
from woob.tools.capabilities.bank.transactions import FrenchTransaction


class ErrorPage(JsonPage):
    # Defines 'message', 'domain', 'label' and 'error'.
    # 'error' seems to be the stricter version, we'll use that
    # to identify the error. 'label' is the most liberal of all
    # fields, we'll use that as the description.

    def build_doc(self, content):
        if not content:
            # Can sometimes be empty.
            return {}

        return super().build_doc(content)

    def get_error(self):
        return Dict("error")(self.doc)

    def get_error_message(self):
        return Dict("label", default=None)(self.doc)


class LoginPage(RawPage):
    pass


class AuthenticatePage(JsonPage):
    def get_polling_id(self):
        return Dict("returnId")(self.doc)


class AuthenticateStatusPage(JsonPage):
    def get_polling_status(self):
        return Dict("message", default=None)(self.doc)


class AuthenticateCheckPage(JsonPage):
    def get_next_step(self):
        return Dict("nextStep")(self.doc)


class PublicPropertiesPage(JsonPage):
    def get_captcha_key(self):
        return self.doc["commonUrl"]["google.captcha.v2.site.key.front"]

    def get_redirect_url(self):
        return self.doc["commonUrl"]["marketpay.cemacarteRedirection"]


class HomePage(LoggedPage, RawPage):
    pass


class ProfilePage(JsonPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_id = CleanText(Dict("customer/externalId"))

        obj_firstname = CleanText(Dict("customer/firstName"))
        obj_lastname = CleanText(Dict("customer/lastName"))
        obj_maiden_name = CleanText(Dict("personView/maidenName"))
        obj_birth_date = Date(CleanText(Dict("personView/birthDate")))
        obj_nationality = CleanText(Dict("personView/nationalityName"))
        obj_gender = Map(
            CleanText(Dict("customer/salutation")),
            {"MISTER": "Male", "MISS": "Female"},
            default=NotAvailable,
        )

        obj_email = CleanText(Dict("personView/email"))  # jea*.***@***.fr
        obj_phone = CleanText(Dict("personView/mobilePhone"))

        obj_job = CleanText(Dict("personView/occupation"))
        obj_job_start_date = Date(
            CleanText(
                Dict("personView/employmentContractStartDate"),
            )
        )


ACCOUNT_TYPES = {
    "CHECKING_ACCOUNT": Account.TYPE_CHECKING,
}


class AccountsPage(JsonPage):
    @method
    class iter_accounts(DictElement):
        item_xpath = "current-account"

        class item(ItemElement):
            klass = Account

            obj__equipmentId = Dict("equipmentId")
            obj_id = obj_number = Dict("accountNumber")
            obj_label = Dict("standardLabel")
            obj_balance = CleanDecimal(Dict("availableBalance"))
            obj_currency = Currency(Dict("currency"))

            obj_type = Map(
                Dict("accountType"),
                ACCOUNT_TYPES,
                Account.TYPE_UNKNOWN,
            )


TRANSACTION_TYPES = {
    "VIRREC": FrenchTransaction.TYPE_TRANSFER,
    "VIREMI": FrenchTransaction.TYPE_TRANSFER,
    "PAICBP": FrenchTransaction.TYPE_CARD,
    "FACSER": FrenchTransaction.TYPE_BANK,
}


class OperationsPage(JsonPage):
    @method
    class iter_operations(DictElement):
        def find_elements(self):
            # Operations in this document are organized by date, then
            # local index. We ought to iterate over these.

            for per_date in self.el["accountOperations"].values():
                for transaction_element in per_date:
                    yield transaction_element

        class item(ItemElement):
            klass = FrenchTransaction

            obj_date = Date(Dict("date"))
            obj_amount = CleanDecimal(Dict("transactionAmount"))
            obj_label = Dict("remittanceInformation")

            def obj_rdate(self):
                return Date(Dict("operationDate", default=Dict("date")(self)))(self)

            def obj_raw(self):
                raw = Dict("lib2", default=None)(self)
                label = Field("label")(self)
                if not raw:
                    return label
                elif raw == label:
                    return raw
                else:
                    return "%s %s" % (raw, label)

            obj_type = Map(
                Dict("type", default=None),
                TRANSACTION_TYPES,
                default=FrenchTransaction.TYPE_UNKNOWN,
            )


class TransferValidatePage(JsonPage):
    def get_transfer_status(self):
        return CleanText(Dict("transferStatus"))(self.doc)


class TransferValidateCumulativePage(RawPage):
    pass


class TransferValidateUnitPage(RawPage):
    pass


class TransferExecutePage(JsonPage):
    def get_transfer_status(self):
        return CleanText(Dict("transferExecutionStatus"))(self.doc)


TRANSFER_STATUS = {
    "VALIDATED": TransferStatus.DONE,
}


class TransferHistoryPage(JsonPage):
    @method
    class iter_transfers(DictElement):
        item_xpath = "historicalTransferOperationViews"

        class item(ItemElement):
            klass = Transfer

            def parse(self, el):
                creation_date = DateTime(CleanText(Dict("creationDate")))(el)
                self.env["creation_date"] = creation_date
                self.env["creation_timestamp"] = creation_date.timestamp()

            # The actual 'id' field varies at every query; we want to use
            # 'initiatorCustomerId' (a numeric value) and 'creationDate'
            # (an ISO datetime with timezone) here.
            obj_id = Format(
                "%s-%.3f",
                CleanText(Dict("initiatorCustomerId")),
                Env("creation_timestamp"),
            )
            obj_creation_date = Env("creation_date")
            obj_status = Map(
                CleanText(Dict("status")),
                TRANSFER_STATUS,
                default=TransferStatus.UNKNOWN,
            )

            obj_label = CleanText(Dict("motive"))
            obj_amount = CleanDecimal.SI(Dict("amount"))
            obj_currency = Currency(Dict("currency"))

            # This identifier should only be used to query the TransferPage,
            # since it changes everytime.
            obj__id = CleanText(Dict("id"))


class TransferDebitAccountsPage(JsonPage):
    def get_account_id(self, account_number):
        """Get the account identifier for a given account number."""

        for element in self.doc:
            if element["accountNumber"] == account_number:
                return element["accountId"]


class TransferOngoingPage(JsonPage):
    @method
    class iter_transfers(TransferHistoryPage.iter_transfers.klass):
        item_xpath = "transfers"

        # TODO: We haven't actually got an example of such an array.
        #       Once we do, we will be able to mark the differences from the
        #       transfer history here.


class TransferPage(JsonPage):
    @method
    class get_transfer(ItemElement):
        klass = Transfer

        obj_status = Map(
            CleanText(Dict("status")),
            TRANSFER_STATUS,
            default=TransferStatus.UNKNOWN,
        )
        obj_exec_date = Date(CleanText(Dict("deadlineDate")))

        obj_label = CleanText(Dict("motif"))
        obj_amount = CleanDecimal.SI(Dict("amount"))
        obj_currency = Currency(Dict("currency"))

        obj_recipient_id = CleanText(Dict("transferBeneficiaryId"))

        def obj_date_type(self):
            is_immediate = Dict("immediate")(self)

            if is_immediate:
                return TransferDateType.FIRST_OPEN_DAY

            raise AssertionError("Non-immediate transfer")


class RecipientsPage(JsonPage):
    def get_recipient_id(self, iban_or_id):
        """
        Get the identifier of a recipient for use for a transfer.
        """

        for recipients_key in ("recentRecipients", "allRecipients"):
            for recipient in self.doc[recipients_key]:
                if not recipient.get("ibans"):  # None or empty list
                    continue

                if iban_or_id == recipient["elementId"]:
                    return recipient["ibans"][0]["ibanOnBeneficiaryId"]

                for iban in recipient["ibans"]:
                    if iban_or_id in (
                        iban["transferBeneficiaryId"],
                        iban["ibanOnBeneficiaryId"],
                        iban["iban"],
                    ):
                        return iban["ibanOnBeneficiaryId"]

    @method
    class iter_transfer_recipients(DictElement):
        item_xpath = "allRecipients"

        class item(ItemElement):
            klass = Recipient

            def condition(self):
                # Filter out the current account.
                if not self.env.get("account_number"):
                    return True

                recipient_number = CleanText(
                    Dict(
                        "accountNumber",
                        default="",
                    )
                )(self.el)

                return (
                    not recipient_number
                    or "account_number" not in self.env
                    or recipient_number != self.env["account_number"]
                )

            obj_id = Coalesce(
                CleanText(Dict("accountNumber", default="")),
                CleanText(Dict("iban", default="")),
            )

            obj_label = CleanText(Dict("label"))
            obj_category = Map(
                CleanText(Dict("type")),
                {
                    "CUSTOMER_INTERNAL_ACCOUNT": "Interne",
                    "BENEFICIARY_WITH_IBAN": "Externe",
                },
                default=NotAvailable,
            )
            obj_iban = Coalesce(
                CleanText(Dict("iban", default="")),
                default=None,
            )

            # Not actually the date at which the recipients are enabled at,
            # but the closest thing we have, so we'll use it.
            obj_enabled_at = Date(CleanText(Dict("lastUpdateDate")))


class CreateRecipientPage(JsonPage):
    def get_inwebo_session_id(self):
        return CleanText(Dict("inweboSessionId"))(self.doc)

    def get_beneficiary_id(self):
        return CleanText(Dict("transferBeneficiaryId"))(self.doc)


class VerifyRecipientCreatedPage(RawPage):
    pass
