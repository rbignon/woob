# Copyright(C) 2016  Romain Bignon
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

from deprecated.sphinx import deprecated
from schwifty import BBAN, IBAN
from schwifty.exceptions import InvalidAccountCode


@deprecated(version="3.8", reason="Use :class:`schwifty.IBAN.compact` instead.")
def clean(iban: str) -> str:
    return IBAN(iban).compact


@deprecated(version="3.8", reason="Use :attr:`schwifty.IBAN.is_valid` instead.")
def is_iban_valid(iban: str) -> bool:
    # Ensure upper alphanumeric input.
    return IBAN(iban, allow_invalid=True).is_valid


@deprecated(version="3.8", reason="Use :attr:`schwifty.IBAN.numeric` instead.")
def iban2numeric(iban: str) -> int:
    return IBAN(iban).numeric


@deprecated(version="3.8", reason="Use :attr:`schwifty.IBAN.checksum_digits` instead.")
def find_iban_checksum(iban: str) -> int:
    return int(IBAN(iban).checksum_digits)


@deprecated(version="3.8", reason="Use :meth:`schwifty.IBAN.from_bban` instead.")
def rebuild_iban(iban: str) -> str:
    return str(IBAN.from_bban(iban[:2], iban[4:]))


# For helper functions below, a RIB is French BBAN


@deprecated(version="3.8", reason="Use :meth:`schwifty.IBAN.from_bban` instead.")
def rib2iban(rib: str) -> str:
    return str(IBAN.from_bban("FR", rib))


@deprecated(
    version="3.8", reason="Use :attr:`schwifty.BBAN.national_checksum_digits` instead."
)
def find_rib_checksum(bank: str, counter: str, account: str) -> int:
    return int(
        BBAN.from_components(
            "FR", bank_code=bank, branch_code=counter, account_code=account
        ).national_checksum_digits
    )


@deprecated(version="3.8", reason="Use :meth:`schwifty.IBAN.from_bban` instead.")
def is_rib_valid(rib: str) -> bool:
    bban = BBAN("FR", rib)
    if len(bban) > 23:
        return False

    try:
        # Function raises if there is an issue. The bool is something else.
        bban.validate_national_checksum()
    except InvalidAccountCode:
        return False
    return True


@deprecated(version="3.8", reason="Use :meth:`schwifty.BBAN.from_components` instead.")
def rebuild_rib(rib: str) -> str:
    bban = BBAN("FR", rib)
    return BBAN.from_components(
        "FR",
        bank_code=bban.bank_code,
        branch_code=bban.branch_code,
        account_code=bban.account_code,
    ).compact
