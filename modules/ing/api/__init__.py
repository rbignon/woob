# Copyright(C) 2019 Sylvie Ye
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

# flake8: compatible

from .accounts_page import AccountInfoPage, AccountsPage, ComingPage, HistoryPage, InvestTokenPage, LifeInsurancePage
from .login import LoginPage
from .profile_page import ProfilePage
from .transfer_page import (
    AddRecipientPage,
    ConfirmOtpPage,
    CreditAccountsPage,
    DebitAccountsPage,
    OtpChannelsPage,
    TransferPage,
)


__all__ = [
    "LoginPage",
    "AccountsPage",
    "HistoryPage",
    "ComingPage",
    "AccountInfoPage",
    "InvestTokenPage",
    "LifeInsurancePage",
    "DebitAccountsPage",
    "CreditAccountsPage",
    "TransferPage",
    "AddRecipientPage",
    "OtpChannelsPage",
    "ConfirmOtpPage",
    "ProfilePage",
]
