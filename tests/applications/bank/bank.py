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

import io
import logging

from woob.applications.bank.bank import OfxFormatter
from woob.capabilities.bank import Account


def test_account_type_ofx_mapping():
    """Basic Account types are mapped to valid OFX ACCTTYPE values."""
    account = Account()
    buffer = io.StringIO()
    formatter = OfxFormatter(outfile=buffer)

    account.type = Account.TYPE_CHECKING
    formatter.start_format(account=account)
    assert "<ACCTTYPE>CHECKING" in buffer.getvalue()

    account.type = Account.TYPE_SAVINGS
    buffer.truncate()
    formatter.start_format(account=account)
    assert "<ACCTTYPE>SAVINGS" in buffer.getvalue()


def test_account_type_default_ofx_mapping(caplog):
    """Unmapped Account types are mapped to valid OFX format values."""
    account = Account()
    buffer = io.StringIO()
    formatter = OfxFormatter(outfile=buffer)

    account.type = -1
    with caplog.at_level(logging.ERROR, logger="woob.applications.bank.bank"):
        formatter.start_format(account=account)
        assert "<ACCTTYPE>CHECKING" in buffer.getvalue()
        assert "cannot be mapped to OFX format" in caplog.text
