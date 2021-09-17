# -*- coding: utf-8 -*-

# Copyright(C) 2009-2012  Romain Bignon
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

from decimal import Decimal

from woob.tools.capabilities.bank.transactions import AmericanTransaction


def test_american():
    clean_amount = AmericanTransaction.clean_amount
    assert clean_amount('42') == '42'
    assert clean_amount('42,12') == '42.12'
    assert clean_amount('42.12') == '42.12'
    assert clean_amount('$42.12 USD') == '42.12'
    assert clean_amount('$12.442,12 USD') == '12442.12'
    assert clean_amount('$12,442.12 USD') == '12442.12'

    decimal_amount = AmericanTransaction.decimal_amount
    assert decimal_amount('$12,442.12 USD') == Decimal('12442.12')
    assert decimal_amount('') == Decimal('0')
