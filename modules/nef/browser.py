# Copyright(C) 2019      Damien Cassou
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

import datetime

from woob.browser import URL, need_login
from woob.browser.mfa import TwoFactorBrowser
from woob.exceptions import BrowserIncorrectPassword, OTPSentType, SentOTPQuestion

from .pages import AccountsPage, FinalizeLoginPage, HomePage, LoginHomePage, LoginPage, RecipientsPage, TransactionsPage


def next_week_string():
    return (datetime.date.today() + datetime.timedelta(weeks=1)).strftime("%Y-%m-%d")


class NefBrowser(TwoFactorBrowser):
    BASEURL = "https://espace-client.lanef.com"

    home = URL("/templates/home.cfm", HomePage)
    main = URL("/templates/main.cfm", HomePage)
    download = URL(
        r"/templates/account/accountActivityListDownload.cfm\?viewMode=CSV&orderBy=TRANSACTION_DATE_DESCENDING&page=1&startDate=2016-01-01&endDate=%s&showBalance=true&AccNum=(?P<account_id>.*)"
        % next_week_string(),
        TransactionsPage,
    )
    login_home = URL("/templates/logon/logon.cfm", LoginHomePage)
    login = URL("/Gateway.cfc", LoginPage)
    finalize = URL(r"/templates/logon/checkPasswordMatrixToken.cfm", FinalizeLoginPage)

    __states__ = ("login_token",)

    def __init__(self, config, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.login_token = None
        self.otp_sms = config["otp_sms"].get()

        self.AUTHENTICATION_METHODS = {
            "otp_sms": self.handle_sms,
        }

    def locate_browser(self, state):
        if self.otp_sms:
            return
        super().locate_browser(state)

    def init_login(self):
        self.login_home.go()
        self.login_token = self.page.get_login_token()
        self.login.go(
            data={
                "method": "logonAuthentication",
                "logonId": self.username,
                "userId": self.username,
                "subUserId": "",
                "factor": "LOGPAS",
                "password": self.password,
            }
        )

        if self.page.is_wrongpass():
            # returns ["error","Utilisateur ou mot de passe invalide"]
            raise BrowserIncorrectPassword(self.page.get_wrongpass_message())

        if self.page.is_otp():
            # returns ["OTPSMS"]
            raise SentOTPQuestion(
                "otp_sms",
                medium_type=OTPSentType.SMS,
                message="Mot de passe à usage unique (en cas de non réception, veuillez contacter votre conseiller)",
            )

        if self.page.is_login_only_password():
            # no otp needed
            return self.finalize_login()

        raise AssertionError("Something unexpected happened during login")

    def handle_sms(self):
        self.login.go(
            data={
                "method": "logonAuthentication",
                "logonId": self.username,
                "userId": self.username,
                "subUserId": "",
                "factor": "OTPSMS",
                "otpVal": self.otp_sms,
            }
        )

        if self.page.is_wrongpass():
            # returns ["error","Mot de passe &agrave; usage unique invalide."]
            raise BrowserIncorrectPassword(self.page.get_wrongpass_message())

        if self.page.is_code_expired():
            raise BrowserIncorrectPassword()

        if not self.page.is_otp():
            raise AssertionError("Unexpected error during otp validation")

        self.finalize_login()

    def finalize_login(self):
        self.finalize.go(
            data={
                "FACTOR": "OTPSMS",
                "logonToken": self.login_token,
                "USERID": self.username,
                "SUBUSERID": "",
                "STATIC": self.password,
                "OTP": self.otp_sms,
                "AUTOMATEDID": "",
            }
        )

        if not self.home.is_here():
            raise AssertionError("We should be redirected to the home page")

    @need_login
    def iter_accounts_list(self):
        response = self.main.open(data={"templateName": "account/accountList.cfm"})

        page = AccountsPage(self, response)
        return page.get_items()

    @need_login
    def iter_transactions_list(self, account):
        return self.download.go(account_id=account.id).iter_history()

    # CapBankTransfer
    @need_login
    def iter_recipients_list(self):
        response = self.main.open(data={"templateName": "beneficiary/beneficiaryList.cfm", "LISTTYPE": "HISTORY"})

        page = RecipientsPage(self, response)
        return page.get_items()
