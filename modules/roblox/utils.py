# flake8: compatible

# Copyright(C) 2022 Thomas Touhey <thomas@touhey.fr>
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

import re

from woob.browser.exceptions import ClientError

EMAIL_REGEX = re.compile(r'^\w+([-_+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*$')
PHONE_NUMBER_REGEX = re.compile(r'^[\d|\W|_]+$')
MINIMUM_PHONE_LENGTH = 4


class InvalidSessionError(ClientError):
    """An invalid session error was encountered."""

    pass


def is_valid_email(email):
    """Determines if the email is valid the same way the website does.

    The same validation method is used as on the website.
    Do not modify unless the website modifies it.
    """

    return EMAIL_REGEX.fullmatch(email)


def is_valid_phone_number(number):
    """Determines if the phone number is valid.

    The same validation method is used as on the website.
    Do not modify unless the website modifies it.
    """

    if not number or len(number) < MINIMUM_PHONE_LENGTH:
        return False
    if re.search(r'\d', number) is None:
        return False
    return PHONE_NUMBER_REGEX.fullmatch(number)


def get_username_type(username):
    """Determines the username type.

    Does it the same way the website's loginService does.
    """

    if is_valid_email(username):
        return 'Email'
    if is_valid_phone_number(username):
        return 'PhoneNumber'
    return 'Username'
