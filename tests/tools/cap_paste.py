# -*- coding: utf-8 -*-

# Copyright(C) 2011-2021 woob project
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

from woob.tools.capabilities.paste import BasePasteModule, bin_to_b64


def test_expiration():
    class MockPasteModule(BasePasteModule):
        def __init__(self, expirations):
            self.EXPIRATIONS = expirations

    # all expirations are too high
    assert MockPasteModule({1337: '', 42: '', False: ''}).get_closest_expiration(1) is None
    # we found a suitable lower or equal expiration
    assert MockPasteModule({1337: '', 42: '', False: ''}).get_closest_expiration(84) == 42
    assert MockPasteModule({1337: '', 42: '', False: ''}).get_closest_expiration(False) is False
    assert MockPasteModule({1337: '', 42: ''}).get_closest_expiration(False) == 1337
    assert MockPasteModule({1337: '', 42: '', False: ''}).get_closest_expiration(1336) == 42
    assert MockPasteModule({1337: '', 42: '', False: ''}).get_closest_expiration(1337) == 1337
    assert MockPasteModule({1337: '', 42: '', False: ''}).get_closest_expiration(1338) == 1337
    # this format should work, though of doubtful usage
    assert MockPasteModule([1337, 42, False]).get_closest_expiration(84) == 42


def test_b64():
    assert bin_to_b64(b"\x00" * 10) == "AAAAAAAAAAAAAA=="
