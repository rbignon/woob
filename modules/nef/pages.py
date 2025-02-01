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

import re

from woob.browser.elements import DictElement, ItemElement, ListElement, TableElement, method
from woob.browser.filters.html import Attr, TableCell
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, CleanText, Date, Field, Regexp
from woob.browser.pages import CsvPage, HTMLPage, JsonPage, LoggedPage, PartialHTMLPage
from woob.capabilities.bank import Account, Recipient
from woob.tools.date import parse_french_date

from .transaction import Transaction


class LoginHomePage(HTMLPage):
    def get_login_token(self):
        return Attr('//input[@name="logonToken"]', "value")(self.doc)


class LoginPage(JsonPage):
    def is_wrongpass(self):
        return Dict("0")(self.doc) == "error" and "invalide" in Dict("1")(self.doc)

    def is_code_expired(self):
        return Dict("0")(self.doc) == "error" and "Expired_One_Time_Password" in Dict("1")(self.doc)

    def is_otp(self):
        return Dict("0")(self.doc) == "OTPSMS"

    def is_login_only_password(self):
        return Dict("0")(self.doc) == "LOGPAS"

    def get_wrongpass_message(self):
        return Dict("1")(self.doc)


class FinalizeLoginPage(JsonPage):
    pass


class HomePage(LoggedPage, HTMLPage):
    pass


class AccountsPage(LoggedPage, PartialHTMLPage):
    ACCOUNT_TYPES = {
        re.compile(r"livret"): Account.TYPE_SAVINGS,
        re.compile(r"parts sociales"): Account.TYPE_MARKET,
    }

    @method
    class get_items(ListElement):
        item_xpath = '//div[@data-type="account"]'

        class item(ItemElement):
            klass = Account

            obj_id = CleanText('.//div/div/div[(position()=3) and (has-class("pc-content-text"))]/span') & Regexp(
                pattern=r"(\d+) "
            )
            obj_label = CleanText('.//div/div/div[(position()=2) and (has-class("pc-content-text-wrap"))]')
            obj_balance = CleanDecimal("./div[position()=3]/span", replace_dots=True)
            obj_currency = "EUR"

            def obj_type(self):
                label = Field("label")(self).lower()

                for regex, account_type in self.page.ACCOUNT_TYPES.items():
                    if regex.match(label):
                        return account_type

                return Account.TYPE_UNKNOWN


class RecipientsPage(LoggedPage, PartialHTMLPage):
    @method
    class get_items(TableElement):
        head_xpath = '//table[@id="tblBeneficiaryList"]/thead//td'
        item_xpath = '//table[@id="tblBeneficiaryList"]//tr[has-class("beneficiary-data-rows")]'

        col_label = re.compile("Nom.*")
        col_iban = re.compile("IBAN.*")

        class item(ItemElement):
            klass = Recipient

            obj_id = Attr(".", "beneficiaryid")
            obj_label = CleanText(TableCell("label"))
            obj_iban = CleanText(TableCell("iban"))


class TransactionsPage(LoggedPage, CsvPage):
    ENCODING = "latin-1"
    DIALECT = "excel"

    # lines 1 to 5 are meta-data
    # line 6 is empty
    # line 7 describes the columns
    HEADER = 7

    @method
    class iter_history(DictElement):
        class item(ItemElement):
            klass = Transaction

            # The CSV contains these columns:
            #
            # "Date opération","Date Valeur","Référence","Montant","Solde","Libellé"
            obj_raw = Transaction.Raw(Dict("Libellé"))
            obj_amount = CleanDecimal(Dict("Montant"), replace_dots=True)
            obj_date = Date(Dict("Date opération"), parse_func=parse_french_date, dayfirst=True)
            obj_vdate = Date(Dict("Date Valeur"), parse_func=parse_french_date, dayfirst=True)
