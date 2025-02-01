# -*- coding: utf-8 -*-

# Copyright(C) 2021      Vincent A
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

import string


alphabet = f"{string.digits}{string.ascii_uppercase}{string.ascii_lowercase}"
for remove in "O0Il":
    alphabet = alphabet.replace(remove, "")
alphabet = alphabet.encode("ascii")


ralphabet = {b: n for n, b in enumerate(alphabet)}


def encode(input):
    input = int.from_bytes(input, "big")
    output = bytearray()
    while input:
        input, index = divmod(input, 58)
        output.append(alphabet[index])
    return bytes(reversed(output))


def decode(input):
    nb = sum(ralphabet[val] * 58**pos for pos, val in enumerate(reversed(input)))
    output = bytearray()
    # warning: might ignore trailing nulls
    while nb:
        nb, b = divmod(nb, 256)
        output.append(b)
    return bytes(reversed(output))
