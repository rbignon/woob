# Copyright(C) 2009-2011  Romain Bignon, Christophe Benz
#
# This file is part of woob.
#
# woob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# woob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with woob. If not, see <http://www.gnu.org/licenses/>.

import datetime
import logging
import uuid
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation

from dateutil.parser import parse as parse_date
from dateutil.relativedelta import relativedelta
from lxml import etree as ET
from lxml.builder import E

from woob.capabilities.bank import (
    Account,
    AddRecipientStep,
    CapBank,
    CapTransfer,
    Recipient,
    Transaction,
    Transfer,
    TransferInvalidAmount,
    TransferInvalidDate,
    TransferInvalidEmitter,
    TransferInvalidLabel,
    TransferInvalidRecipient,
    TransferStep,
)
from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.base import empty, find_object
from woob.capabilities.captcha import exception_to_job
from woob.capabilities.profile import CapProfile
from woob.core.bcall import CallErrors
from woob.exceptions import AppValidationCancelled, AppValidationExpired, CaptchaQuestion, DecoupledValidation
from woob.tools.application.captcha import CaptchaMixin
from woob.tools.application.formatters.iformatter import IFormatter, PrettyFormatter
from woob.tools.application.repl import ReplApplication, defaultcount
from woob.tools.misc import to_unicode


__all__ = ["Appbank"]
LOGGER = logging.getLogger(__name__)


class OfxFormatter(IFormatter):
    MANDATORY_FIELDS = ("id", "date", "rdate", "label", "raw", "amount", "category")
    TYPES_ACCTS = {
        Account.TYPE_CHECKING: "CHECKING",
        Account.TYPE_SAVINGS: "SAVINGS",
        Account.TYPE_DEPOSIT: "DEPOSIT",
        Account.TYPE_LOAN: "LOAN",
        Account.TYPE_MARKET: "MARKET",
        Account.TYPE_JOINT: "JOINT",
        Account.TYPE_CARD: "CARD",
    }
    TYPES_TRANS = {
        Transaction.TYPE_TRANSFER: "XFER",
        Transaction.TYPE_ORDER: "PAYMENT",
        Transaction.TYPE_CHECK: "CHECK",
        Transaction.TYPE_DEPOSIT: "DEP",
        Transaction.TYPE_PAYBACK: "OTHER",
        Transaction.TYPE_WITHDRAWAL: "ATM",
        Transaction.TYPE_CARD: "POS",
        Transaction.TYPE_INSTANT: "POS",
        Transaction.TYPE_LOAN_PAYMENT: "INT",
        Transaction.TYPE_BANK: "FEE",
    }

    balance = Decimal(0)
    coming = Decimal(0)
    account_type = ""
    seen = set()

    def start_format(
        self,
        account: Account,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> None:
        self.balance = account.balance
        self.coming = account.coming
        self.account_type = account.type

        if self.account_type not in self.TYPES_ACCTS:
            LOGGER.error(
                "Account %s type cannot be mapped to OFX format. Will default to %s",
                account,
                account.TYPE_CHECKING,
            )
            self.account_type = account.TYPE_CHECKING

        self.output('<?xml version="1.0" encoding="UTF-8" standalone="no"?>')
        self.output(
            f'<?OFX OFXHEADER="200" VERSION="220" SECURITY="NONE" OLDFILEUID="NONE" NEWFILEUID="{uuid.uuid1()}"?>'
        )
        self.document = E.OFX(
            E.SIGNONMSGSRSV1(
                E.SONRS(E.STATUS(E.CODE("0"), E.SEVERITY("INFO"))),
                E.DTSERVER(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")),
                E.LANGUAGE("ENG"),
            ),
        )

        bank_acct_from = []
        if self.account_type == Account.TYPE_CARD:

            bank_acct_from = [E.ACCTID(account.iban.account_code)]
            if account.iban.national_checksum_digits:
                bank_acct_from.append(E.ACCTKEY(account.iban.national_checksum_digits))

            message = E.CREDITCARDMSGSRSV1(
                E.CCSTMTTRNRS(
                    E.TRNUID(str(uuid.uuid1())),
                    E.STATUS(E.CODE("0"), E.SEVERITY("INFO")),
                    E.CCSTMTRS(
                        E.CURDEF(account.currency or "EUR"),
                        E.CCBANKACCTFROM(*bank_acct_from),
                    ),
                )
            )
            stmtrs = message.find(".//CCSTMTRS")

        else:
            bank_acct_from = [E.BANKID(account.iban.bank_code)]
            if account.iban.branch_code:
                bank_acct_from.append(E.BRANCHID(account.iban.branch_code))
            bank_acct_from.append(E.ACCTID(account.iban.account_code))
            bank_acct_from.append(E.ACCTTYPE(self.TYPES_ACCTS[self.account_type]))
            if account.iban.national_checksum_digits:
                bank_acct_from.append(E.ACCTKEY(account.iban.national_checksum_digits))

            message = E.BANKMSGSRSV1(
                E.STMTTRNRS(
                    E.TRNUID(str(uuid.uuid1())),
                    E.STATUS(E.CODE("0"), E.SEVERITY("INFO")),
                    E.STMTRS(
                        E.CURDEF(account.currency or "EUR"),
                        E.BANKACCTFROM(*bank_acct_from),
                    ),
                )
            )
            stmtrs = message.find(".//STMTRS")

        stmtrs.extend(
            [
                E.BANKTRANLIST(  # Statement-transaction
                    E.DTSTART(start_date.strftime("%Y%m%d")),
                    E.DTEND(end_date.strftime("%Y%m%d")),
                ),
                E.BANKTRANLISTP(),  # Pending statement transaction
                E.LEDGERBAL(
                    E.BALAMT(str(self.balance)),
                    E.DTASOF(datetime.date.today().strftime("%Y%m%d")),
                ),
            ]
        )

        try:
            available_balance = E.BALAMT(str(self.balance + self.coming))
        except TypeError:
            available_balance = E.BALAMT(str(self.balance))

        stmtrs.append(
            E.AVAILBAL(
                available_balance,
                E.DTASOF(datetime.date.today().strftime("%Y%m%d")),
            )
        )
        self.document.append(message)
        self.stmtrs = stmtrs

    def format_obj(self, obj, alias):
        stmt = E.STMTTRN()

        # special case of coming operations with card ID
        if obj.coming and hasattr(obj, "obj._cardid") and not empty(obj._cardid):
            stmt.append(E.TRNTYPE(obj._cardid))
        elif obj.type in self.TYPES_TRANS:
            stmt.append(E.TRNTYPE(self.TYPES_TRANS[obj.type]))
        else:
            stmt.append(E.TRNTYPE("DEBIT" if obj.amount < 0 else "CREDIT"))

        stmt.append(E.DTPOSTED(obj.date.strftime("%Y%m%d")))
        if obj.rdate:
            stmt.append(E.DTUSER(obj.rdate.strftime("%Y%m%d")))
        stmt.append(E.TRNAMT(str(obj.amount)))

        if obj.type == Transaction.TYPE_LOAN_PAYMENT:
            if hasattr(obj, "_loan_payment"):
                _loan = E.LOANPMTINFO(
                    E.PRINAMT(str(obj._loan_payment["principal_amount"])),
                    E.INTAMT(str(obj._loan_payment["interest_amount"])),
                )
                if obj._loan_payment["insurance_amount"]:
                    _loan.append(E.INSURANCE(str(obj._loan_payment["insurance_amount"])))
                stmt.append(_loan)
            else:
                LOGGER.warning("Loan payment not implemented for this backend.")

        stmt.append(E.FITID(obj.id or obj.unique_id(self.seen)))
        if hasattr(obj, "_ref") and not empty(obj._ref):
            stmt.append(E.REFNUM(obj._ref))

        if hasattr(obj, "label") and not empty(obj.label):
            stmt.append(E.NAME(obj.label))
        else:
            stmt.append(E.NAME(obj.raw))

        if hasattr(obj, "_recipient") and not empty(obj._recipient):
            _transfer = [E.BANKID(obj._recipient.iban.bank_code)]
            if obj._recipient.iban.branch_code:
                _transfer.append(E.BRANCHID(obj._recipient.iban.branch_code))
            _transfer.append(E.ACCTID(obj._recipient.iban.account_code))
            # schwifty supports extracting this information via account_type property,
            # however it does not work for all countries. It also does not map the value to an enum.
            # OFX specification requires this field so set an acceptable default: CHECKING.
            _transfer.append(E.ACCTTYPE("CHECKING"))
            if obj._recipient.iban.national_checksum_digits:
                _transfer.append(E.ACCTKEY(obj._recipient.iban.national_checksum_digits))
            stmt.append(E.BANKACCTTO(*_transfer))

        if hasattr(obj, "_memo") and not empty(obj._memo):
            stmt.append(E.MEMO(obj._memo))
        elif obj.category:
            stmt.append(E.MEMO(obj.category))

        self.stmtrs.find(".//BANKTRANLIST").append(stmt)
        return

    def flush(self):
        self.output(ET.tostring(self.document, encoding="UTF-8", pretty_print=True).decode("utf-8"))


class QifFormatter(IFormatter):
    MANDATORY_FIELDS = ("id", "date", "raw", "amount")

    def start_format(self, **kwargs):
        self.output("!Type:Bank")

    def format_obj(self, obj, alias):
        result = "D%s\n" % obj.date.strftime("%d/%m/%y")
        result += "T%s\n" % obj.amount
        if hasattr(obj, "category") and not empty(obj.category):
            result += "N%s\n" % obj.category
        result += "M%s\n" % obj.raw
        result += "^"
        return result


class PrettyQifFormatter(QifFormatter):
    MANDATORY_FIELDS = ("id", "date", "raw", "amount", "category")

    def start_format(self, **kwargs):
        self.output("!Type:Bank")

    def format_obj(self, obj, alias):
        if hasattr(obj, "rdate") and not empty(obj.rdate):
            result = "D%s\n" % obj.rdate.strftime("%d/%m/%y")
        else:
            result = "D%s\n" % obj.date.strftime("%d/%m/%y")
        result += "T%s\n" % obj.amount

        if hasattr(obj, "category") and not empty(obj.category):
            result += "N%s\n" % obj.category

        if hasattr(obj, "label") and not empty(obj.label):
            result += "M%s\n" % obj.label
        else:
            result += "M%s\n" % obj.raw

        result += "^"
        return result


class TransactionsFormatter(IFormatter):
    MANDATORY_FIELDS = ("date", "label", "amount")
    TYPES = [
        "",
        "Transfer",
        "Order",
        "Check",
        "Deposit",
        "Payback",
        "Withdrawal",
        "Card",
        "Loan",
        "Bank",
        "Cash deposit",
        "Card summary",
        "Deferred card",
    ]

    def start_format(self, **kwargs):
        self.output(" Date         Category     Label                                                  Amount ")
        self.output("------------+------------+---------------------------------------------------+-----------")

    def format_obj(self, obj, alias):
        if hasattr(obj, "category") and obj.category:
            _type = obj.category
        else:
            try:
                _type = self.TYPES[obj.type]
            except (IndexError, AttributeError):
                _type = ""

        label = obj.label or ""
        if not label and hasattr(obj, "raw"):
            label = obj.raw or ""
        date = obj.date.strftime("%Y-%m-%d") if not empty(obj.date) else ""
        amount = obj.amount or Decimal("0")
        return " {}   {} {} {}".format(
            self.colored("%-10s" % date, "blue"),
            self.colored("%-12s" % _type[:12], "magenta"),
            self.colored("%-50s" % label[:50], "yellow"),
            self.colored("%10.2f" % amount, "green" if amount >= 0 else "red"),
        )


class TransferFormatter(IFormatter):
    MANDATORY_FIELDS = ("id", "exec_date", "account_label", "recipient_label", "amount")
    DISPLAYED_FIELDS = ("label", "account_iban", "recipient_iban", "currency")

    def format_obj(self, obj, alias):
        result = "------- Transfer %s -------\n" % obj.fullid
        result += "Date:       %s\n" % obj.exec_date
        if obj.account_iban:
            result += f"Origin:     {obj.account_label} ({obj.account_iban})\n"
        else:
            result += "Origin:     %s\n" % obj.account_label

        if obj.recipient_iban:
            result += f"Recipient:  {obj.recipient_label} ({obj.recipient_iban})\n"
        else:
            result += "Recipient:  %s\n" % obj.recipient_label

        result += "Amount:     {:.2f} {}\n".format(obj.amount, obj.currency or "")
        if obj.label:
            result += "Label:      %s\n" % obj.label
        return result


class TransferListFormatter(IFormatter):
    def format_obj(self, obj, alias):
        result = [
            "From: %s" % self.colored("%-20s" % obj.account_label, "red"),
            " Label: %s\n" % self.colored(obj.label, "yellow"),
            "To: %s" % self.colored("%-22s" % obj.recipient_label, "green"),
            " Amount: %s\n" % self.colored(obj.amount, "red"),
            "Date: %s" % self.colored(obj.exec_date, "yellow"),
            " Status: %s" % self.colored(obj.status, "yellow"),
            "\n",
        ]
        return "".join(result)


class InvestmentFormatter(IFormatter):
    MANDATORY_FIELDS = ("label", "quantity", "unitvalue")
    DISPLAYED_FIELDS = ("code", "diff")

    tot_valuation = Decimal(0)
    tot_diff = Decimal(0)

    def start_format(self, **kwargs):
        self.output(" Label                            Code          Quantity     Unit Value   Valuation    diff    ")
        self.output("-------------------------------+--------------+------------+------------+------------+---------")

    def check_emptyness(self, obj):
        if not empty(obj):
            return (obj, "%11.2f")
        return ("---", "%11s")

    def format_obj(self, obj, alias):
        label = obj.label

        if not empty(obj.diff):
            diff = obj.diff
        elif not empty(obj.quantity) and not empty(obj.unitprice):
            diff = obj.valuation - (obj.quantity * obj.unitprice)
        else:
            diff = "---"
            format_diff = "%8s"
        if isinstance(diff, Decimal):
            format_diff = "%8.2f"
            self.tot_diff += diff

        if not empty(obj.quantity):
            quantity = obj.quantity
            format_quantity = "%11.2f"
            if obj.quantity == obj.quantity.to_integral():
                format_quantity = "%11d"
        else:
            format_quantity = "%11s"
            quantity = "---"

        unitvalue, format_unitvalue = self.check_emptyness(obj.unitvalue)
        valuation, format_valuation = self.check_emptyness(obj.valuation)
        if isinstance(valuation, Decimal):
            self.tot_valuation += obj.valuation

        if empty(obj.code) and not empty(obj.description):
            code = obj.description
        else:
            code = obj.code

        return " {}  {}  {}  {}  {}  {}".format(
            self.colored("%-30s" % label[:30], "red"),
            self.colored("%-12s" % code[:12], "yellow") if not empty(code) else " " * 12,
            self.colored(format_quantity % quantity, "yellow"),
            self.colored(format_unitvalue % unitvalue, "yellow"),
            self.colored(format_valuation % valuation, "yellow"),
            self.colored(format_diff % diff, "green" if not isinstance(diff, str) and diff >= 0 else "red"),
        )

    def flush(self):
        self.output("-------------------------------+--------------+------------+------------+------------+---------")
        self.output(
            "                                                                  Total  %s %s"
            % (
                self.colored("%11.2f" % self.tot_valuation, "yellow"),
                self.colored("%9.2f" % self.tot_diff, "green" if self.tot_diff >= 0 else "red"),
            )
        )
        self.tot_valuation = Decimal(0)
        self.tot_diff = Decimal(0)


class RecipientListFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ("id", "label")
    DISPLAYED_FIELDS = ("iban", "bank_name")

    def start_format(self, **kwargs):
        self.output("Available recipients:")

    def get_title(self, obj):
        details = " - ".join(filter(None, (obj.iban, obj.bank_name)))
        if details:
            return f"{obj.label} ({details})"
        return obj.label


class AdvisorListFormatter(IFormatter):
    MANDATORY_FIELDS = ("id", "name")

    def start_format(self, **kwargs):
        self.output("   Bank           Name                           Contacts")
        self.output("-----------------+------------------------------+-----------------------------------------")

    def format_obj(self, obj, alias):
        bank = obj.backend
        phones = ""
        contacts = []
        if not empty(obj.phone):
            phones += obj.phone
        if not empty(obj.mobile):
            if phones != "":
                phones += " or %s" % obj.mobile
            else:
                phones += obj.mobile
        if phones:
            contacts.append(phones)

        for attr in ("email", "agency", "address"):
            value = getattr(obj, attr)
            if not empty(value):
                contacts.append(value)

        if len(contacts) > 0:
            first_contact = contacts.pop(0)
        else:
            first_contact = ""

        result = "  {} {} {} ".format(
            self.colored("%-15s" % bank, "yellow"),
            self.colored("%-30s" % obj.name, "red"),
            self.colored("%-30s" % first_contact, "green"),
        )
        for contact in contacts:
            result += "\n {} {}".format((" ") * 47, self.colored("%-25s" % contact, "green"))

        return result


class AccountListFormatter(IFormatter):
    MANDATORY_FIELDS = ("id", "label", "balance", "coming", "type")

    totals = {}

    def start_format(self, **kwargs):
        self.output(
            "               %s  Account                     Balance    Coming "
            % ((" " * 15) if not self.interactive else "")
        )
        self.output(
            "------------------------------------------%s+----------+----------"
            % (("-" * 15) if not self.interactive else "")
        )

    def format_obj(self, obj, alias):
        if alias is not None:
            id = "{} ({})".format(
                self.colored("%3s" % ("#" + alias), "red", "bold"),
                self.colored(obj.backend, "blue", "bold"),
            )
            clean = f"#{alias} ({obj.backend})"
            if len(clean) < 15:
                id += " " * (15 - len(clean))
        else:
            id = self.colored("%30s" % obj.fullid, "red", "bold")

        balance = obj.balance or Decimal("0")
        coming = obj.coming or Decimal("0")
        currency = obj.currency or "EUR"
        result = "{} {} {}  {}".format(
            id,
            self.colored("%-25s" % obj.label[:25], "yellow" if obj.type != Account.TYPE_LOAN else "blue"),
            (
                self.colored("%9.2f" % obj.balance, "green" if balance >= 0 else "red")
                if not empty(obj.balance)
                else " " * 9
            ),
            self.colored("%9.2f" % obj.coming, "green" if coming >= 0 else "red") if not empty(obj.coming) else "",
        )

        currency_totals = self.totals.setdefault(currency, {})
        currency_totals.setdefault("balance", Decimal(0))
        currency_totals.setdefault("coming", Decimal(0))

        if obj.type != Account.TYPE_LOAN:
            currency_totals["balance"] += balance
            currency_totals["coming"] += coming
        return result

    def flush(self):
        self.output(
            "------------------------------------------%s+----------+----------"
            % (("-" * 15) if not self.interactive else "")
        )
        for currency, currency_totals in sorted(
            self.totals.items(), key=lambda k_v: (k_v[1]["balance"], k_v[1]["coming"], k_v[0])
        ):
            balance = currency_totals["balance"]
            coming = currency_totals["coming"]

            self.output(
                "%s                              Total (%s)   %s   %s"
                % (
                    (" " * 15) if not self.interactive else "",
                    currency,
                    self.colored("%8.2f" % balance, "green" if balance >= 0 else "red"),
                    self.colored("%8.2f" % coming, "green" if coming >= 0 else "red"),
                )
            )
        self.totals.clear()


class EmitterListFormatter(IFormatter):
    MANDATORY_FIELDS = ("id", "label", "currency")

    def start_format(self, **kwargs):
        self.output(
            "       %s  Emitter              Currency   Number Type      Number     Balance "
            % ((" " * 15) if not self.interactive else "")
        )
        self.output(
            "----------------------------%s+----------+-------------+-------------+----------+"
            % (("-" * 15) if not self.interactive else "")
        )

    def format_emitter_number(self, obj):
        account_number = " " * 11
        if obj.number_type != "unknown" and obj.number:
            account_number = f"{obj.number[:4]}***{obj.number[len(obj.number) - 4 :]}"
        return account_number

    def format_obj(self, obj, alias):
        if alias is not None:
            obj_id = "%s" % self.colored("%3s" % ("#" + alias), "red", "bold")
        else:
            obj_id = self.colored("%30s" % obj.fullid, "red", "bold")

        balance = " " * 9
        if not empty(obj.balance):
            balance = self.colored("%9.2f" % obj.balance, "green" if obj.balance >= 0 else "red")

        account_number = self.format_emitter_number(obj)

        return "{} {} {} {} {} {}".format(
            obj_id,
            self.colored("%-25s" % obj.label[:25], "yellow", "bold"),
            self.colored("%-10s" % obj.currency, "green", "bold"),
            self.colored("%-13s" % obj.number_type, "blue", "bold"),
            self.colored("%-11s" % account_number, "blue", "bold"),
            balance,
        )

    def flush(self):
        self.output(
            "----------------------------%s+----------+-------------+-------------+----------+"
            % (("-" * 15) if not self.interactive else "")
        )


class Appbank(CaptchaMixin, ReplApplication):
    APPNAME = "bank"
    OLD_APPNAME = "boobank"
    VERSION = "3.7"
    COPYRIGHT = "Copyright(C) 2010-YEAR Romain Bignon, Christophe Benz"
    CAPS = CapBank
    DESCRIPTION = (
        "Console application allowing to list your bank accounts and get their balance, "
        "display accounts history and coming bank operations, and transfer money from an account to "
        "another (if available)."
    )
    SHORT_DESCRIPTION = "manage bank accounts"
    EXTRA_FORMATTERS = {
        "account_list": AccountListFormatter,
        "recipient_list": RecipientListFormatter,
        "transfer": TransferFormatter,
        "qif": QifFormatter,
        "pretty_qif": PrettyQifFormatter,
        "ofx": OfxFormatter,
        "ops_list": TransactionsFormatter,
        "investment_list": InvestmentFormatter,
        "advisor_list": AdvisorListFormatter,
        "transfer_list": TransferListFormatter,
        "emitter_list": EmitterListFormatter,
    }
    DEFAULT_FORMATTER = "table"
    COMMANDS_FORMATTERS = {
        "ls": "account_list",
        "list": "account_list",
        "recipients": "recipient_list",
        "transfer": "transfer",
        "history": "ops_list",
        "coming": "ops_list",
        "transfer_history": "transfer_list",
        "investment": "investment_list",
        "advisor": "advisor_list",
        "emitters": "emitter_list",
    }
    COLLECTION_OBJECTS = (
        Account,
        Transaction,
    )

    def bcall_error_handler(self, backend, error, backtrace):
        if isinstance(error, TransferStep):
            params = {}
            for field in error.fields:
                v = self.ask(field)
                params[field.id] = v
            # backend.config['accept_transfer'].set(v)
            params["backends"] = backend
            self.start_format()
            for transfer in self.do("transfer", error.transfer, **params):
                self.format(transfer)
        elif isinstance(error, AddRecipientStep):
            params = {}
            params["backends"] = backend
            for field in error.fields:
                v = self.ask(field)
                params[field.id] = v
            try:
                next(iter(self.do("add_recipient", error.recipient, **params)))
            except CallErrors as e:
                self.bcall_errors_handler(e)
        elif isinstance(error, DecoupledValidation):
            if isinstance(error.resource, Recipient):
                func_name = "add_recipient"
            elif isinstance(error.resource, Transfer):
                func_name = "transfer"
            else:
                print(
                    'Error(%s): The resource should be of type Recipient or Transfer, not "%s"'
                    % (backend.name, type(error.resource)),
                    file=self.stderr,
                )
                return False

            print(error.message)
            params = {
                "backends": backend,
                "resume": True,
            }
            try:
                next(iter(self.do(func_name, error.resource, **params)))
            except CallErrors as e:
                self.bcall_errors_handler(e)
        elif isinstance(error, AppValidationCancelled):
            print(
                "Error({}): {}".format(backend.name, to_unicode(error) or "The app validation has been cancelled"),
                file=self.stderr,
            )
        elif isinstance(error, AppValidationExpired):
            print(
                "Error({}): {}".format(backend.name, to_unicode(error) or "The app validation has expired"),
                file=self.stderr,
            )
        elif isinstance(error, TransferInvalidAmount):
            print(
                "Error({}): {}".format(backend.name, to_unicode(error) or "The transfer amount is invalid"),
                file=self.stderr,
            )
        elif isinstance(error, TransferInvalidLabel):
            print(
                "Error({}): {}".format(backend.name, to_unicode(error) or "The transfer label is invalid"),
                file=self.stderr,
            )
        elif isinstance(error, TransferInvalidEmitter):
            print(
                "Error({}): {}".format(backend.name, to_unicode(error) or "The transfer emitter is invalid"),
                file=self.stderr,
            )
        elif isinstance(error, TransferInvalidRecipient):
            print(
                "Error({}): {}".format(backend.name, to_unicode(error) or "The transfer recipient is invalid"),
                file=self.stderr,
            )
        elif isinstance(error, TransferInvalidDate):
            print(
                "Error({}): {}".format(backend.name, to_unicode(error) or "The transfer execution date is invalid"),
                file=self.stderr,
            )
        elif isinstance(error, CaptchaQuestion):
            if not self.captcha_woob.count_backends():
                print(
                    "Error(%s): Site requires solving a CAPTCHA but no CapCaptchaSolver backends were configured"
                    % backend.name,
                    file=self.stderr,
                )
                return False

            print(
                "Info(%s): Encountered CAPTCHA, please wait for its resolution, it can take dozens of seconds"
                % backend.name,
                file=self.stderr,
            )
            job = exception_to_job(error)
            self.solve_captcha(job, backend)
            return False
        else:
            return super().bcall_error_handler(backend, error, backtrace)

    def load_default_backends(self):
        self.load_backends(CapBank, storage=self.create_storage())

    def _complete_account(self, exclude=None):
        if exclude:
            exclude = "%s@%s" % self.parse_id(exclude)

        return [s for s in self._complete_object() if s != exclude]

    def do_list(self, line):
        """
        list [-U]

        List accounts.
        Use -U to disable sorting of results.
        """
        return self.do_ls(line)

    def show_history(self, command, line):
        id, end_date = self.parse_command_args(line, 2, 1)

        account = self.get_object(id, "get_account", [])
        if not account:
            print('Error: account "%s" not found (Hint: try the command "list")' % id, file=self.stderr)
            return 2

        if end_date is not None:
            try:
                end_date = parse_date(end_date)
            except ValueError:
                print(
                    '"%s" is an incorrect date format (for example "%s")'
                    % (end_date, (datetime.date.today() - relativedelta(months=1)).strftime("%Y-%m-%d")),
                    file=self.stderr,
                )
                return 3
            old_count = self.options.count
            self.options.count = None

        transactions = []
        for transaction in self.do(command, account, backends=account.backend):
            if end_date is not None and transaction.date < end_date:
                break
            transactions.append(transaction)

        self.start_format(
            account=account,
            start_date=transactions[-1].date,
            end_date=datetime.date.today(),
        )

        for transaction in transactions:
            self.format(transaction)

        if end_date is not None:
            self.options.count = old_count

    def complete_history(self, text, line, *ignored):
        args = line.split(" ")
        if len(args) == 2:
            return self._complete_account()

    @defaultcount(10)
    def do_history(self, line):
        """
        history ID [END_DATE]

        Display history of transactions.

        If END_DATE is supplied, list all transactions until this date.
        """
        return self.show_history("iter_history", line)

    def complete_coming(self, text, line, *ignored):
        args = line.split(" ")
        if len(args) == 2:
            return self._complete_account()

    @defaultcount(10)
    def do_coming(self, line):
        """
        coming ID [END_DATE]

        Display future transactions.

        If END_DATE is supplied, show all transactions until this date.
        """
        return self.show_history("iter_coming", line)

    def complete_transfer(self, text, line, *ignored):
        args = line.split(" ")
        if len(args) == 2:
            return self._complete_account()
        if len(args) == 3:
            return self._complete_account(args[1])

    def do_add_recipient(self, line):
        """
        add_recipient iban label

        Add a recipient to a backend.
        """
        if len(self.enabled_backends) > 1:
            print(
                'Error: select a single backend to add a recipient (Hint: try the command "backends only")',
                file=self.stderr,
            )
            return 1
        iban, label, origin_account_id = self.parse_command_args(line, 3, 2)
        recipient = Recipient()
        recipient.iban = iban
        recipient.label = label
        recipient.origin_account_id = origin_account_id
        next(iter(self.do("add_recipient", recipient)))

    def do_recipients(self, line):
        """
        recipients ACCOUNT

        List recipients of ACCOUNT
        """
        (id_from,) = self.parse_command_args(line, 1, 1)

        account = self.get_object(id_from, "get_account", [])
        if not account:
            print("Error: account %s not found" % id_from, file=self.stderr)
            return 1

        self.objects = []

        self.start_format()
        for recipient in self.do("iter_transfer_recipients", account, backends=account.backend, caps=CapTransfer):
            self.cached_format(recipient)

    @contextmanager
    def use_cmd_formatter(self, cmd):
        self.set_formatter(self.commands_formatters.get(cmd, self.DEFAULT_FORMATTER))
        try:
            yield
        finally:
            self.flush()

    def _build_transfer(self, line):
        if self.interactive:
            id_from, id_to, amount, reason, exec_date = self.parse_command_args(line, 5, 0)
        else:
            id_from, id_to, amount, reason, exec_date = self.parse_command_args(line, 5, 3)

        missing = not bool(id_from and id_to and amount)

        if id_from:
            account = self.get_object(id_from, "get_account", [])
            id_from = account.id
            if not account:
                print("Error: account %s not found" % id_from, file=self.stderr)
                return
        else:
            with self.use_cmd_formatter("list"):
                self.do_ls("")
            id_from = self.ask("Transfer money from account", default="")
            if not id_from:
                return
            id_from, backend = self.parse_id(id_from)

            account = find_object(self.objects, fullid=f"{id_from}@{backend}")
            if not account:
                return
            id_from = account.id

        if id_to:
            id_to, backend_name_to = self.parse_id(id_to)
            if account.backend != backend_name_to:
                print("Transfer between different backends is not implemented", file=self.stderr)
                return
            rcpts = self.do("iter_transfer_recipients", id_from, backends=account.backend)
            rcpt = find_object(rcpts, id=id_to)
        else:
            with self.use_cmd_formatter("recipients"):
                self.do_recipients(account.fullid)
            id_to = self.ask("Transfer money to recipient", default="")
            if not id_to:
                return
            id_to, backend = self.parse_id(id_to)

            rcpt = find_object(self.objects, fullid=f"{id_to}@{backend}")
            if not rcpt:
                return

        if not amount:
            amount = self.ask("Amount to transfer", default="", regexp=r"\d+(?:\.\d*)?")
        try:
            amount = Decimal(amount)
        except (TypeError, ValueError, InvalidOperation):
            print("Error: please give a decimal amount to transfer", file=self.stderr)
            return
        if amount <= 0:
            print("Error: transfer amount must be strictly positive", file=self.stderr)
            return

        if missing:
            reason = self.ask("Label of the transfer (seen by the recipient)", default="")
            exec_date = self.ask("Execution date of the transfer (YYYY-MM-DD format, empty for today)", default="")

        today = datetime.date.today()
        if exec_date:
            try:
                exec_date = datetime.datetime.strptime(exec_date, "%Y-%m-%d").date()
            except ValueError:
                print("Error: execution date must be valid and in YYYY-MM-DD format", file=self.stderr)
                return
            if exec_date < today:
                print("Error: execution date cannot be in the past", file=self.stderr)
                return
        else:
            exec_date = today

        transfer = Transfer()
        transfer.backend = account.backend
        transfer.account_id = account.id
        transfer.account_label = account.label
        transfer.account_iban = account.iban
        transfer.recipient_id = id_to
        if rcpt:
            # Try to find the recipient label. It can be missing from
            # recipients list, for example for banks which allow transfers to
            # arbitrary recipients.
            transfer.recipient_label = rcpt.label
            transfer.recipient_iban = rcpt.iban
        transfer.amount = amount
        transfer.label = reason or ""
        transfer.exec_date = exec_date

        return transfer

    def do_transfer(self, line):
        """
        transfer [ACCOUNT RECIPIENT AMOUNT [LABEL [EXEC_DATE]]]

        Make a transfer beetwen two accounts
        - ACCOUNT    the source account
        - RECIPIENT  the recipient
        - AMOUNT     amount to transfer
        - LABEL      label of transfer
        - EXEC_DATE  date when to execute the transfer
        """

        transfer = self._build_transfer(line)
        if transfer is None:
            return 1

        if self.interactive:
            with self.use_cmd_formatter("transfer"):
                self.start_format()
                self.cached_format(transfer)

            if not self.ask("Are you sure to do this transfer?", default=True):
                return

        # only keep basic fields because most modules don't handle others
        transfer.account_label = None
        transfer.account_iban = None
        transfer.recipient_label = None
        transfer.recipient_iban = None

        self.start_format()
        next(iter(self.do("transfer", transfer, backends=transfer.backend)))

    def complete_transfer_history(self, text, line, *ignored):
        return self.complete_history(self, text, line, *ignored)

    @defaultcount(10)
    def do_transfer_history(self, line):
        """
        transfer_history [ACCOUNT_ID]

        Display history of transfer transactions.
        """
        (id,) = self.parse_command_args(line, 1, 0)

        account = None
        backends = None
        if id:
            account = self.get_object(id, "get_account", [])
            if not account:
                print('Error: account "%s" not found (Hint: try the command "list")' % id, file=self.stderr)
                return 2
            backends = account.backend

        self.start_format()
        for tr in self.do("iter_transfers", account, backends=backends):
            self.format(tr)

    def show_wealth(self, command, id):
        account = self.get_object(id, "get_account", [])
        if not account:
            print('Error: account "%s" not found (Hint: try the command "list")' % id, file=self.stderr)
            return 2

        caps = {
            "iter_investment": CapBankWealth,
            "iter_pocket": CapBankWealth,
            "iter_market_orders": CapBankWealth,
        }

        self.start_format()
        for el in self.do(command, account, backends=account.backend, caps=caps[command]):
            self.format(el)

    def do_investment(self, id):
        """
        investment ID

        Display investments of an account.
        """
        self.show_wealth("iter_investment", id)

    def do_pocket(self, id):
        """
        pocket ID

        Display pockets of an account.
        """
        self.show_wealth("iter_pocket", id)

    @defaultcount(10)
    def do_market_order(self, id):
        """
        market_order ID

        Display market orders of an account.
        """
        self.show_wealth("iter_market_orders", id)

    def do_profile(self, line):
        """
        profile

        Display detailed information about person or company.
        """
        self.start_format()
        for profile in self.do("get_profile", caps=CapProfile):
            self.format(profile)

    def do_emitters(self, line):
        """
        emitters

        Display transfer emitter account.
        """
        self.objects = []
        self.start_format()
        for emitter in self.do("iter_emitters", backends=list(self.enabled_backends), caps=CapTransfer):
            self.cached_format(emitter)

    def do_convert_currency(self, line):
        """
        convert_currency FROM_CURRENCY TO_CURRENCY [AMOUNT]

        Convert an amount from a currency to another
        """

        currency_from, currency_to, amount = self.parse_command_args(line, 3, 2)
        if amount is None:
            amount = 1
        amount = Decimal(amount)

        for rate in self.do("get_rate", currency_from, currency_to):
            if rate is not None:
                converted_amount = rate.convert(amount)
                print(f"{amount} {rate.currency_from} is equal to {converted_amount} {rate.currency_to}")
                break

    def main(self, argv):
        self.load_config()
        return super().main(argv)
