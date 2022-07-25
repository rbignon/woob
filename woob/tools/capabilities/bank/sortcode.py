# Copyright(C) 2022      Budget Insight
#
# This file is part of weboob.
#
# weboob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# weboob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with weboob. If not, see <http://www.gnu.org/licenses/>.

import re

from woob.browser.filters.base import Filter, FilterError, debug

__all__ = [
    'SortCodeAccountNumber', 'SortCodeAccountNumberFormatError',
    'canonicalize_sort_code_account_number',
]

STRICT_SORTCODE_ACCOUNT_NUMBER_RE = re.compile(r'\d{14}')
SORTCODE_ACCOUNT_NUMBER_RE = re.compile(
    r'\s*(\d{2})-?(\d{2})-?(\d{2})\s*(\d{4})?\s*(\d{4})\s*',
)


def canonicalize_sort_code_account_number(arg):
    """Return the canonical form of the given sort code account number.

    This function also checks if the provided sort code account number
    is valid, and raises a ValueError in case it is not.
    """
    m = SORTCODE_ACCOUNT_NUMBER_RE.fullmatch(arg)
    if not m:
        raise ValueError(f'{arg!r} is not a valid Sortcode account number')

    return ''.join(m.group(i) for i in range(1, 6))


def is_sort_code_account_number_valid(arg):
    """Return whether the provided sort code account number is valid or not.

    Since this function might be used to check if we want to store the
    provided value or not, we don't want non-canonical values to be validated
    here, and only validate canonical sort code account number representations.
    """
    return bool(STRICT_SORTCODE_ACCOUNT_NUMBER_RE.fullmatch(arg))


class SortCodeAccountNumberFormatError(FilterError):
    pass


class SortCodeAccountNumber(Filter):
    """Return the input only if it is a valid Sortcode account number."""
    @debug()
    def filter(self, code):
        try:
            return canonicalize_sort_code_account_number(code)
        except ValueError:
            return self.default_or_raise(SortCodeAccountNumberFormatError(
                '%r is not a valid sortcode account number, and no ' % code
                + 'default value was set.',
            ))
