# Copyright(C) 2023 Powens
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

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.html import Link
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, CleanText, Date, Format, FromTimestamp, Map, Regexp
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage
from woob.capabilities.bank import Account, Transaction
from woob.capabilities.base import NotAvailable
from woob.tools.capabilities.bank.transactions import FrenchTransaction


class ErrorPage(HTMLPage):
    def get_error(self):
        return CleanText('//div[@class="t-error"]//li/text()')(self.doc)


class LoginPage(HTMLPage):
    def login(self, username, passwd):
        form = self.get_form()
        form["username"] = username
        form["password"] = passwd
        form.submit()

    def get_error_url(self):
        return Link('.//link[contains(@href, "js/app")]')(self.doc)

    def get_error_msg(self, error):
        msg = Regexp(pattern=rf"{error}.+?errorMessage=\"(.+?)\":", default="").filter(self.content.decode("utf-8"))
        if msg:
            return msg
        self.logger.warning("error message not found")


class AccountsPage(LoggedPage, JsonPage):
    def get_end_index(self):
        return self.response.json().get("nbTotalCards")

    @method
    class iter_accounts(DictElement):
        item_xpath = "porteursList"

        class item(ItemElement):
            klass = Account

            def condition(self):
                return FromTimestamp(Dict("closeDate")(self) // 1000)(self).year == 9999

            def obj_label(self):
                civility_id = CleanText(Dict("contract/personne/civility"))(self)

                if civility_id == "1":
                    civility = "M."
                elif civility_id == "2":
                    civility = "Mme"
                elif civility_id == "3":
                    civility = "Mlle"
                else:
                    raise AssertionError("Unexpected civility %s" % civility_id)

                return "{} {} {}".format(
                    civility,
                    CleanText(Dict("contract/personne/firstName"))(self),
                    CleanText(Dict("contract/personne/lastName"))(self),
                )

            obj_id = Format(
                "%s%s", CleanText(Dict("contract/personne/login")), CleanDecimal(Dict("cardNumberEncrypted"))
            )

            obj_type = Account.TYPE_CARD
            obj__card_num = Regexp(Dict("cardNumberEncrypted"), r"(\d+)")
            obj__card_id = Dict("cardId")
            obj_number = CleanText(Dict("cardNumberEncrypted"))
            obj_currency = "EUR"


class PeriodsPage(LoggedPage, JsonPage):
    def get_periods(self):
        return [p["periodeId"] for p in Dict("periodeDebitCreditGestList")(self.doc)]


class HistoryPage(LoggedPage, JsonPage):
    @method
    class iter_history(DictElement):
        class item(ItemElement):
            klass = Transaction

            TYPES = {
                "RETRAIT": Transaction.TYPE_WITHDRAWAL,
                "ACHAT": Transaction.TYPE_CARD,
                "COTIS": Transaction.TYPE_UNKNOWN,
            }

            def condition(self):
                # Check if date is available, if not then we do not return the transaction
                return Dict("echeanceDebitCreditList/echeanceDebitCreditList")(self)

            def obj_date(self):
                if Dict("echeanceDebitCreditList/echeanceDebitCreditList")(self):
                    # The date is in timestamp format but with extra zeros at the end
                    # we muste devide
                    return FromTimestamp(
                        Dict("echeanceDebitCreditList/echeanceDebitCreditList/0/dateEcheance")(self) // 1000
                    )(self)
                return NotAvailable

            obj_raw = Dict("libelle")
            # Default "-" is because some "COTIS" transactions just have " - " as label
            obj_label = Regexp(Dict("libelle"), r"(.+)(?= - )", default="-")
            obj_original_amount = CleanDecimal.French(Dict("mntDevise", default=NotAvailable), default=NotAvailable)
            obj_amount = CleanDecimal.French(Dict("mntEuros"))
            obj_rdate = Date(Dict("date"), dayfirst=True)
            obj_type = Map(Dict("nature"), TYPES, Transaction.TYPE_UNKNOWN)
            obj_original_currency = FrenchTransaction.Currency(Dict("devise"))
