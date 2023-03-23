# Copyright(C) 2010-2011 Romain Bignon
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

from __future__ import annotations

from typing import List

from .base import (
    Capability, BaseObject, StringField, IntField, Field, UserError,
    NotLoadedType, NotAvailableType, NotLoaded
)


__all__ = ['AccountRegisterError', 'Account', 'StatusField', 'CapAccount', 'CapCredentialsCheck']


class AccountRegisterError(UserError):
    """
    Raised when there is an error during registration.
    """


class Account(BaseObject):
    """
    Describe an account and its properties.
    """
    login =         StringField('Login')
    password =      StringField('Password')
    properties =    Field('List of key/value properties', dict)

    def __init__(
        self,
        id: str = '',
        url: str | NotLoadedType | NotAvailableType = NotLoaded
    ):
        super().__init__(id, url)


class StatusField(BaseObject):
    """
    Field of an account staeobjectus.
    """
    FIELD_TEXT    = 0x001     # the value is a long text
    FIELD_HTML    = 0x002     # the value is HTML formated

    key =           StringField('Key')
    label =         StringField('Label')
    value =         StringField('Value')
    flags =         IntField('Flags')

    def __init__(
        self,
        key: str,
        label: str,
        value: str,
        flags: int = 0,
        url: str | NotLoadedType | NotAvailableType = NotLoaded
    ):
        super().__init__(key, url)
        self.__setattr__('key', key)
        self.__setattr__('label', label)
        self.__setattr__('value', value)
        self.__setattr__('flags', flags)


class CapAccount(Capability):
    """
    Capability for websites when you can create and manage accounts.

    :var ACCOUNT_REGISTER_PROPERTIES: This class constant may be a list of
                                      :class:`woob.tools.value.Value` objects.
                                      If the value remains None, woob considers
                                      that :func:`register_account` isn't supported.
    """
    ACCOUNT_REGISTER_PROPERTIES = None

    @staticmethod
    def register_account(account: Account):
        """
        Register an account on website

        This is a static method, it would be called even if the backend is
        instancied.

        :param account: describe the account to create
        :type account: :class:`Account`
        :raises: :class:`AccountRegisterError`
        """
        raise NotImplementedError()

    def confirm_account(self, mail: str):
        """
        From an email go to the confirm link.
        """
        raise NotImplementedError()

    def get_account(self) -> Account:
        """
        Get the current account.
        """
        raise NotImplementedError()

    def update_account(self, account: Account):
        """
        Update the current account.
        """
        raise NotImplementedError()

    def get_account_status(self) -> List[StatusField]:
        """
        Get status of the current account.

        :returns: a list of fields
        :rtype: list[StatusField]
        """
        raise NotImplementedError()


class CapCredentialsCheck(Capability):
    def check_credentials(self) -> bool:
        """
        Its purpose is to check that the credentials (in the config) are valid
        for the module's website, API, whatever requires credentials to be
        accessed.
        """
        raise NotImplementedError()
