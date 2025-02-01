# Copyright(C) 2019      Vincent A
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
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, CleanText, Date
from woob.browser.pages import CsvPage, HTMLPage, LoggedPage
from woob.capabilities.bank import Account, Transaction
from woob.capabilities.base import NotAvailable
from woob.exceptions import BrowserIncorrectPassword


MAIN_ID = "_lendosphere_"


class LoginPage(HTMLPage):
    def do_login(self, username, password):
        form = self.get_form(id="session-new-form")
        form["user[email]"] = username
        form["user[password]"] = password
        form.submit()

    def raise_error(self):
        msg = CleanText('//div[has-class("alert-danger")]')(self.doc)
        if "Votre email ou mot de passe est incorrect" in msg:
            raise BrowserIncorrectPassword(msg)
        assert False, "unhandled error %r" % msg


class SummaryPage(LoggedPage, HTMLPage):
    def get_liquidities(self):
        # 'Mon compte' tag appears 3 times on the page
        return CleanDecimal.French('(//span[@id="current-wallet-amount"])[1]')(self.doc)


class ProfilePage(LoggedPage, HTMLPage):
    pass


class ComingProjectPage(LoggedPage, HTMLPage):
    def iter_projects(self):
        return [value for value in self.doc.xpath('//select[@id="offer"]/option/@value') if value != "*"]


class ComingPage(LoggedPage, CsvPage):
    HEADER = 1

    @method
    class iter_transactions(DictElement):
        class item(ItemElement):
            klass = Transaction

            obj_type = Transaction.TYPE_BANK
            obj_raw = Dict("Projet")
            obj_date = Date(Dict("Date"), dayfirst=True)

            obj_gross_amount = CleanDecimal.SI(Dict("Capital rembourse"))
            obj_amount = CleanDecimal.SI(Dict("Montant brut"))
            obj_commission = CleanDecimal.SI(Dict("Interets"))

            obj__amount_left = CleanDecimal.SI(Dict("Capital restant du"))


class GSummaryPage(LoggedPage, HTMLPage):
    @method
    class get_account(ItemElement):
        klass = Account

        obj_id = MAIN_ID
        obj_currency = "EUR"
        obj_number = NotAvailable
        obj_type = Account.TYPE_CROWDLENDING
        obj_label = "Lendosphere"
        obj__invested = CleanDecimal.French('//tr[td[contains(text(),"chéances restantes")]]/td[last()]')
