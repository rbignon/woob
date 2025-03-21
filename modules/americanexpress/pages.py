# Copyright(C) 2017 Vincent Ardisson
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

from decimal import Decimal

from dateutil.parser import parse as parse_date

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, CleanText, Currency, Date, Env, Eval, Field, Format
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage
from woob.browser.selenium import SeleniumPage
from woob.capabilities.bank import Account, Transaction
from woob.capabilities.base import NotAvailable
from woob.exceptions import ActionNeeded, BrowserUnavailable


def float_to_decimal(f):
    return Decimal(str(f))


def parse_decimal(s):
    # we might get 1,399,680 in rupie indonésienne
    if s.count(",") > 1 and not s.count("."):
        return CleanDecimal(replace_dots=(",", ".")).filter(s)
    # we don't know which decimal format this account will use
    comma = s.rfind(",") > s.rfind(".")
    return CleanDecimal(replace_dots=comma).filter(s)


class NoCardPage(HTMLPage):
    def on_load(self):
        raise ActionNeeded()


class NotFoundPage(HTMLPage):
    def on_load(self):
        alert_header = CleanText('//h1[@class="alert-header"]/span')(self.doc)
        alert_content = CleanText('//p[@class="alert-subtitle"]/span')(self.doc)
        raise BrowserUnavailable(alert_header, alert_content)


class HomeLoginPage(HTMLPage):
    pass


class LoginPage(JsonPage):
    def get_status_code(self):
        # - 0 = OK
        # - 1 = Error
        return CleanDecimal(Dict("statusCode"))(self.doc)

    def get_error_code(self):
        # - LGON001 = Incorrect password
        # - LGON003 = Incorrect password: 'Le code utilisateur ou le mot de passe est erroné. Veuillez essayer de nouveau.' on website
        # - LGON004 = Action needed
        # - LGON005 = Account blocked
        # - LGON008 = ?
        # - LGON010 = Browser unavailable
        # - LGON013 = SCA
        return CleanText(Dict("errorCode"))(self.doc)

    def get_error_message(self):
        return CleanText(Dict("errorMessage"))(self.doc) or CleanText(Dict("debugInfo", default=""))(self.doc)

    def get_redirect_url(self):
        return CleanText(Dict("redirectUrl"))(self.doc)

    def get_reauth(self):
        return Dict("reauth")(self.doc)


class ReadAuthChallengePage(JsonPage):
    def get_challenge(self):
        return Dict("challenge")(self.doc)

    def get_account_token(self):
        identity_data = Dict("identityData")(self.doc)
        assert len(identity_data) == 1, "How can we have multiple identity_data?"
        return identity_data[0]["identityValue"]

    def get_otp_methods(self):
        return Dict("tenuredChannels")(self.doc)


class UpdateAuthTokenPage(JsonPage):
    def get_pending_challenges(self):
        return Dict("pendingChallenges")(self.doc)


class AccountsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):
        def find_elements(self):
            for obj in self.page.doc.get("accounts", []):
                obj["_history_token"] = obj["account_token"]
                yield obj
                for secondary_acc in obj.get("supplementary_accounts", []):
                    # Secondary accounts use the id of the parrent account
                    # when searching history/coming. History/coming are filtered
                    # on the owner name (_idforJSON).
                    secondary_acc["_history_token"] = obj["account_token"]
                    yield secondary_acc

        class item(ItemElement):
            klass = Account

            def condition(self):
                return any(status == "Active" for status in Dict("status/account_status")(self))

            obj_id = Dict("account_token")
            obj__history_token = Dict("_history_token")
            obj__account_type = Dict("account/relationship")
            obj_number = Format("-%s", Dict("account/display_account_number"))
            obj_type = Account.TYPE_CARD
            obj_currency = Currency(Env("currency"))
            obj__idforJSON = Dict("profile/embossed_name")

            def obj_label(self):
                if Dict("account/relationship")(self) == "SUPP":
                    return Format(
                        "%s %s",
                        Dict("platform/amex_region"),
                        Dict("profile/embossed_name"),
                    )(self)
                return CleanText(Dict("product/description"))(self)


class JsonBalances(LoggedPage, JsonPage):
    @method
    class fill_balances(ItemElement):
        # coming is what should be refunded at a future deadline
        obj_coming = CleanDecimal.US(Dict("0/total_debits_balance_amount"), sign="-")
        # balance is what is currently due
        obj_balance = CleanDecimal.US(Dict("0/remaining_statement_balance_amount"), sign="-")


class JsonBalances2(LoggedPage, JsonPage):
    @method
    class fill_balances(ItemElement):
        obj_coming = CleanDecimal.US(Dict("0/total/debits_total_amount"), sign="-")
        obj_balance = CleanDecimal.US(Dict("0/total/payments_credits_total_amount"), sign="-")
        # warning: payments_credits_total_amount is not the coming value here


class CurrencyPage(LoggedPage, JsonPage):
    def get_currency(self):
        return self.doc["localeSettings"]["currency_code"]


class JsonPeriods(LoggedPage, JsonPage):
    def get_periods(self):
        return [p["statement_end_date"] for p in self.doc]


class JsonHistory(LoggedPage, JsonPage):
    def get_count(self):
        return self.doc["total_count"]

    @method
    class iter_history(DictElement):
        item_xpath = "transactions"

        class item(ItemElement):
            klass = Transaction

            def obj_type(self):
                if Field("raw")(self) in self.page.browser.SUMMARY_CARD_LABEL:
                    return Transaction.TYPE_CARD_SUMMARY
                elif Field("amount")(self) > 0:
                    return Transaction.TYPE_ORDER
                else:
                    return Transaction.TYPE_DEFERRED_CARD

            obj_raw = CleanText(Dict("description", default=""))

            def obj_date(self):
                # 'statement_end_date' might be absent from this json,
                # we must match the rdate with the right date period
                _date = Date(Dict("statement_end_date", default=None), default=NotAvailable)(self)
                if not _date:
                    periods = Env("periods")(self)
                    for period in periods:
                        period_end_date = parse_date(period).date()
                        if Field("vdate")(self) and Field("vdate")(self) <= period_end_date:
                            _date = period_end_date
                            continue
                return _date

            obj_rdate = Date(Dict("charge_date"))
            obj_vdate = obj_bdate = Date(Dict("post_date", default=None), default=NotAvailable)
            obj_amount = Eval(lambda x: -float_to_decimal(x), Dict("amount"))
            obj_original_currency = Dict("foreign_details/iso_alpha_currency_code", default=NotAvailable)
            obj_commission = CleanDecimal(
                Dict("foreign_details/commission_amount", default=NotAvailable), sign="-", default=NotAvailable
            )
            obj__owner = Dict("embossed_name")
            obj_id = Dict("reference_id", default=NotAvailable)

            def obj_original_amount(self):
                # amount in the account's currency
                amount = Field("amount")(self)
                # amount in the transaction's currency
                original_amount = Dict("foreign_details/amount", default=NotAvailable)(self)
                if Field("original_currency")(self) == "XAF":
                    original_amount = abs(CleanDecimal(replace_dots=(".")).filter(original_amount))
                elif not original_amount:
                    return NotAvailable
                else:
                    original_amount = abs(parse_decimal(original_amount))
                if amount < 0:
                    return -original_amount
                else:
                    return original_amount

            obj__ref = Dict("identifier")


class SHomePage(SeleniumPage):
    pass


class SLoginPage(SeleniumPage):
    pass
