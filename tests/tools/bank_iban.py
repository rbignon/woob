# -*- coding: utf-8 -*-

# Copyright(C) 2016-2021  Romain Bignon
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

from woob.tools.capabilities.bank.iban import rebuild_iban, rebuild_rib


def test_rebuild():
    assert rebuild_iban('FR0013048379405300290000355') == "FR7613048379405300290000355"
    assert rebuild_iban('GB87BARC20658244971655') == "GB87BARC20658244971655"
    assert rebuild_rib('30003021990005077567600') == "30003021990005077567667"
