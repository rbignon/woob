# Copyright(C) 2022 woob project
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
import io
import logging
import re
from decimal import Decimal

from schwifty import IBAN

from woob.applications.bank.bank import OfxFormatter
from woob.capabilities.bank import Account, Recipient, Transaction
from woob.capabilities.base import NotAvailable


def test_ofx_header():
    """OFX 2.2 header compliance."""
    account = Account()
    buffer = io.StringIO()
    formatter = OfxFormatter(outfile=buffer)
    formatter.termrows = 0

    account.iban = IBAN.random()
    account.type = Account.TYPE_CHECKING
    formatter.start_format(account=account)
    formatter.flush()
    assert '<?OFX OFXHEADER="200" VERSION="220"' in buffer.getvalue()


def test_account_type_ofx_mapping():
    """Basic Account types are mapped to valid OFX ACCTTYPE values."""
    account = Account()
    buffer = io.StringIO()
    formatter = OfxFormatter(outfile=buffer)
    formatter.termrows = 0

    account.iban = IBAN.random()
    account.type = Account.TYPE_CHECKING
    formatter.start_format(account=account)
    formatter.flush()
    assert "<ACCTTYPE>CHECKING</ACCTTYPE>" in buffer.getvalue()

    account.type = Account.TYPE_SAVINGS
    buffer.truncate()
    formatter.start_format(account=account)
    formatter.flush()
    assert "<ACCTTYPE>SAVINGS</ACCTTYPE>" in buffer.getvalue()


def test_account_type_default_ofx_mapping(caplog):
    """Unmapped Account types are mapped to valid OFX format values."""
    account = Account()
    buffer = io.StringIO()
    formatter = OfxFormatter(outfile=buffer)
    formatter.termrows = 0

    account.iban = IBAN.random()
    account.type = -1
    with caplog.at_level(logging.ERROR, logger="woob.applications.bank.bank"):
        formatter.start_format(account=account)
        formatter.flush()
        assert "<ACCTTYPE>CHECKING</ACCTTYPE>" in buffer.getvalue()
        assert "cannot be mapped to OFX format" in caplog.text


def test_ofx_tr_posted_simple_format():
    """Format a very simple posted transaction."""
    buffer = io.StringIO()
    formatter = OfxFormatter(outfile=buffer)
    formatter.termrows = 0
    today = datetime.datetime.now()

    account = Account()
    account.iban = IBAN.random()

    formatter.start_format(account=account)

    tr = Transaction()
    tr.date = today - datetime.timedelta(days=1)
    tr.type = Transaction.TYPE_CARD
    tr.label = "ACME INC"
    tr.amount = Decimal("-15.42")
    formatter.format(tr)

    tr = Transaction()
    tr.date = today - datetime.timedelta(days=1)
    tr.type = -1  # Test default transaction type mapping
    tr.label = "JENKINS GROUP"
    tr.amount = Decimal("-42.15")
    formatter.format(tr)

    formatter.flush()
    output = re.findall(r"<STMTTRN>.+?</STMTTRN>", buffer.getvalue(), re.DOTALL)
    assert "<TRNTYPE>POS</TRNTYPE>" in output[0]
    assert "<TRNAMT>-15.42</TRNAMT>" in output[0]
    assert "<NAME>ACME INC</NAME>" in output[0]

    assert "<TRNTYPE>DEBIT</TRNTYPE>" in output[1]
    assert "<TRNAMT>-42.15</TRNAMT>" in output[1]
    assert "<NAME>JENKINS GROUP</NAME>" in output[1]


def test_ofx_tr_with_memo():
    """Format a transaction with MEMO / motive."""
    buffer = io.StringIO()
    formatter = OfxFormatter(outfile=buffer)
    formatter.termrows = 0
    today = datetime.datetime.now()

    account = Account()
    account.iban = IBAN.random()

    formatter.start_format(account=account)

    tr = Transaction()
    tr.date = today - datetime.timedelta(days=1)
    tr.type = Transaction.TYPE_CARD
    tr.label = "ACME INC"
    tr.amount = Decimal("-15.42")
    tr._memo = "06xxxxxx01 MANDAT XYZ"  # phone recurring payment with SEPA mandate
    formatter.format(tr)

    formatter.flush()
    assert "<MEMO>06xxxxxx01 MANDAT XYZ</MEMO>" in buffer.getvalue()


def test_ofx_tr_with_ref():
    """Format a transaction with a reference."""
    buffer = io.StringIO()
    formatter = OfxFormatter(outfile=buffer)
    formatter.termrows = 0
    today = datetime.datetime.now()

    account = Account()
    account.iban = IBAN.random()

    formatter.start_format(account=account)

    tr = Transaction()
    tr.date = today - datetime.timedelta(days=1)
    tr.type = Transaction.TYPE_ORDER
    tr.label = "ACME INC"
    tr.amount = Decimal("-99.98")
    tr._ref = "BILL-XYZ-1"
    formatter.format(tr)

    formatter.flush()
    assert "<REFNUM>BILL-XYZ-1</REFNUM>" in buffer.getvalue()


def test_ofx_tr_posted_loan_payment_format(caplog):
    """Format a loan payment transaction."""
    buffer = io.StringIO()
    formatter = OfxFormatter(outfile=buffer)
    formatter.termrows = 0
    today = datetime.datetime.now()

    account = Account()
    account.iban = IBAN.random()

    formatter.start_format(account=account)

    tr = Transaction()
    tr.date = today - datetime.timedelta(days=1)
    tr.type = Transaction.TYPE_LOAN_PAYMENT
    tr.label = "Loan #123"
    tr.amount = Decimal("-1342.56")

    with caplog.at_level(logging.WARNING, logger="woob.applications.bank.bank"):
        formatter.format(tr)
        assert "Loan payment not implemented for this backend." in caplog.text

    tr.date = today - datetime.timedelta(days=30)
    tr._loan_payment = {
        "principal_amount": Decimal("1164.42"),
        "interest_amount": Decimal("178.14"),
        "insurance_amount": NotAvailable,
        "principal_balance": NotAvailable,
    }
    formatter.format(tr)

    tr.date = today - datetime.timedelta(days=2)
    tr.label = "Loan #111"
    tr.amount = Decimal("-100.00")
    tr._loan_payment = {
        "principal_amount": Decimal("98.00"),
        "interest_amount": Decimal("1.00"),
        "insurance_amount": Decimal("1.00"),
        "principal_balance": NotAvailable,
    }
    formatter.format(tr)

    formatter.flush()
    output = re.findall(r"<STMTTRN>.+?</STMTTRN>", buffer.getvalue(), re.DOTALL)
    assert "LOANPMTINFO" not in output[0]
    assert "<TRNTYPE>INT</TRNTYPE>" in output[0]
    assert "<TRNAMT>-1342.56</TRNAMT>" in output[0]
    assert "<NAME>Loan #123</NAME>" in output[0]

    assert "LOANPMTINFO" in output[1]
    assert "<PRINAMT>1164.42</PRINAMT>" in output[1]
    assert "<INTAMT>178.14</INTAMT>" in output[1]

    assert "<INSURANCE>1.00</INSURANCE>" in output[2]


def test_ofx_tr_posted_transfer_format():
    """Format a fund transfer transaction."""
    buffer = io.StringIO()
    formatter = OfxFormatter(outfile=buffer)
    formatter.termrows = 0
    today = datetime.datetime.now()

    account = Account()
    account.iban = IBAN.random()

    formatter.start_format(account=account)

    tr = Transaction()
    tr.date = today - datetime.timedelta(days=1)
    tr.type = Transaction.TYPE_TRANSFER
    tr.label = "John Doe"
    tr.amount = Decimal("-1000.00")
    tr._recipient = Recipient()
    tr._recipient.iban = IBAN.random(country_code="DE")
    formatter.format(tr)

    tr._recipient.iban = IBAN.random(country_code="FR")
    formatter.format(tr)

    formatter.flush()
    output = re.findall(r"<STMTTRN>.+?</STMTTRN>", buffer.getvalue(), re.DOTALL)
    assert "<TRNTYPE>XFER</TRNTYPE>" in output[0]
    assert "<TRNAMT>-1000.00</TRNAMT>" in output[0]
    assert "<NAME>John Doe</NAME>" in output[0]
    assert "<BRANCHID>" not in output[0]
    assert "<ACCTKEY>" not in output[0]

    assert f"<BRANCHID>{tr._recipient.iban.branch_code}</BRANCHID>" in output[1]
    assert f"<ACCTID>{tr._recipient.iban.account_code}</ACCTID>" in output[1]
    assert "<ACCTKEY>" in output[1]
