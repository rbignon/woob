# flake8: compatible

# Copyright(C) 2024 Thomas Touhey <thomas@touhey.fr>
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

__all__ = ["naive_deobfuscate", "obfuscate"]

SYS4 = (
    "\\'\"$ -!#%&()*,./:;?@[]^_`{|}~¡¦¨¯´¸¿+<=>±«»×÷¢£¤¥§©¬®°µ¶·0¼½¾1¹2²3³456"
    + "789aAªáÁàÀâÂäÄãÃåÅæÆbBcCçÇdDðÐeEéÉèÈêÊëËfFfgGhHiIíÍìÌîÎïÏjJkKlLmMnNñÑoO"
    + "ºóÓòÒôÔöÖõÕøØpPqQrRsSßtTþÞuUúÚùÙûÛüÜvVwWxXyYýÝÿzZ"
)
SYS5 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def get_obfuscation_code(letter: str) -> str:
    """Get the one or two letter obfuscation code for the character.

    :param letter: The letter to get the obfuscated code for.
    :return: The obfuscated code corresponding to the letter.
    """
    code = SYS4.find(letter)
    if code < 0:
        return SYS5[code % 32]

    return SYS5[code // 32 :][:1] + SYS5[code % 32]


def obfuscate(text: str) -> str:
    """Obfuscate the given text the same way the site does.

    This algorithm is used to obfuscate text in various places, notably
    the login and password in the cookies, and some puzzle data so that
    any user cannot see the solution or other elements when opening
    the page source.

    Note that while most characters will yield two characters with such
    an algorithm, characters that are not in the SYS4 array will simply
    yield 'v'. This is because to obtain the position, the Javascript
    code uses String.prototype.indexOf, which returns -1 if the character
    is not found; while the division per 32 should return no character,
    the modulo gives 31, and 'v' is SYS5[31].

    Equivalent of t2c() in system_v1.js.

    :param text: The text to obfuscate.
    :return: The obfuscated text.
    """
    return "".join(map(get_obfuscation_code, text))


def naive_deobfuscate(obfuscated_text):
    """De-obfuscate the given obfuscated text the same way the site does.

    This reverses the algorithm described previously, but supposes
    there are no unknown characters that have been replaced by 'v'.

    Equivalent of c2t() in system_v1.js.
    """
    return "".join(
        SYS4[SYS5.find(c1) * 32 + SYS5.find(c2)] for c1, c2 in zip(obfuscated_text[::2], obfuscated_text[1::2])
    )
