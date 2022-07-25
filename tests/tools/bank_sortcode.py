# -*- coding: utf-8 -*-

# Copyright(C) 2022 Budget Insight
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

import pytest

from woob.tools.capabilities.bank.sortcode import canonicalize_sort_code_account_number


@pytest.mark.parametrize('inp,outp', (
    ('12-34-56 01234567', '12345601234567'),
    ('12345601234567', '12345601234567'),
    ('  12-34-56 0123 4567  ', '12345601234567'),
))
def test_canonicalize(inp, outp):
    assert canonicalize_sort_code_account_number(inp) == outp


@pytest.mark.parametrize('inp', (
    '12-34-56',
    '12-34-56 1234-5678',
    '123456',
    '12345A12345678',
))
def test_canonicalize_invalid(inp):
    with pytest.raises(ValueError):
        canonicalize_sort_code_account_number(inp)
