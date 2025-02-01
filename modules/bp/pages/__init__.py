# Copyright(C) 2010-2011 Nicolas Duhamel
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

# flake8: compatible

from .accounthistory import AccountHistory, CardsJsonDetails, CardsList, TemporaryPage
from .accountlist import AccountList, AccountRIB, Advisor
from .login import (
    AccountDesactivate,
    BadLoginPage,
    CheckPassword,
    DecoupledPage,
    Initident,
    LoginPage,
    PersonalLoanRoutagePage,
    SmsPage,
    TwoFAPage,
    UnavailablePage,
    Validated2FAPage,
    repositionnerCheminCourant,
)
from .subscription import DownloadPage, ProSubscriptionPage, SubscriptionPage
from .transfer import (
    CerticodePlusSubmitDevicePage,
    CompleteTransfer,
    ConfirmPage,
    CreateRecipient,
    Loi6902TransferPage,
    OtpErrorPage,
    ProTransferChooseAccounts,
    RcptSummary,
    TransferChooseAccounts,
    TransferConfirm,
    TransferSummary,
    ValidateCountry,
    ValidateRecipient,
)


__all__ = [
    "LoginPage",
    "Initident",
    "CheckPassword",
    "repositionnerCheminCourant",
    "AccountList",
    "AccountHistory",
    "BadLoginPage",
    "AccountDesactivate",
    "TransferChooseAccounts",
    "CompleteTransfer",
    "TransferConfirm",
    "TransferSummary",
    "UnavailablePage",
    "CardsList",
    "AccountRIB",
    "Advisor",
    "CreateRecipient",
    "ValidateRecipient",
    "ValidateCountry",
    "ConfirmPage",
    "RcptSummary",
    "SubscriptionPage",
    "DownloadPage",
    "ProSubscriptionPage",
    "Validated2FAPage",
    "TwoFAPage",
    "SmsPage",
    "DecoupledPage",
    "Loi6902TransferPage",
    "CerticodePlusSubmitDevicePage",
    "OtpErrorPage",
    "PersonalLoanRoutagePage",
    "TemporaryPage",
    "CardsJsonDetails",
    "ProTransferChooseAccounts",
]
