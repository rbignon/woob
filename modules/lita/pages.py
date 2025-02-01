# -*- coding: utf-8 -*-

# Copyright(C) 2021      Damien Ramelet
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

from woob.browser.elements import ItemElement, method
from woob.browser.filters.standard import CleanDecimal, CleanText, Currency, Date, Env, Field, Regexp
from woob.browser.pages import HTMLPage, LoggedPage
from woob.capabilities.address import PostalAddress
from woob.capabilities.bank import Account
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.profile import Person


class LoginPage(HTMLPage):
    def do_login(self, username, password):
        form = self.get_form(id="new_user")
        form["user[email]"] = username
        form["user[password]"] = password
        form.submit()

    def get_error_msg(self):
        return CleanText('//p[contains(text(), "mot de passe incorrect")]')(self.doc)


class DashboardPage(LoggedPage, HTMLPage):
    def get_account(self):
        """Lita is an investment platform. There isn't such a notion of accounts, so building a fake account from user information."""
        account = Account()
        account.label = CleanText('//p[@class="mb-0 font-gotham-bold purple"]')(self.doc)
        account.balance = CleanDecimal.French(
            CleanText('//div[contains(text(), "Montant total investi")]//span[@class="text-right"]')
        )(self.doc)
        account.currency = Currency(
            CleanText('//div[contains(text(), "Montant total investi")]//span[@class="text-right"]')
        )(self.doc)
        yield account


class ProfilePage(LoggedPage, HTMLPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_email = CleanText('distinct-values(//input[@name="investor[email]"]/@value)')
        obj_birth_date = Date(CleanText('distinct-values(//input[@name="investor[person_birthdate]"]/@value)'))
        obj_firstname = CleanText('distinct-values(//input[@name="investor[person_first_name]"]/@value)')
        obj_lastname = CleanText('distinct-values(//input[@name="investor[person_last_name]"]/@value)')
        obj_nationality = CleanText('//select[@name="investor[person_nationality]"]/option[@selected="selected"]')
        obj_phone = CleanText('distinct-values(//input[@name="investor[person_phone]"]/@value)')
        obj_gender = CleanText('//select[@name="investor[person_civility]"]/option[@selected="selected"]')

        class obj_postal_address(ItemElement):
            klass = PostalAddress

            obj_street = CleanText('distinct-values(//input[@name="investor[person_address]"]/@value)')
            obj_postal_code = CleanText('distinct-values(//input[@name="investor[person_zip_code]"]/@value)')
            obj_city = CleanText('distinct-values(//input[@name="investor[person_city]"]/@value)')
            obj_country = CleanText('distinct-values(//input[@name="investor[person_country]"]/@value)')


class InvestmentsListPage(LoggedPage, HTMLPage):
    def iter_investments(self):
        for block in self.doc.xpath(
            '//div[contains(@class, "my-investment-table")]//div[contains(@class, "card-white")]'
        ):
            label = CleanText('.//span[contains(@class, "purple")]')(block)
            _id = Regexp(CleanText('.//a[contains(@href, "shares")]/@href'), r"(?P<id>\d+)")(block)
            yield _id, label


class InvestmentsDetailsPage(LoggedPage, HTMLPage):
    @method
    class get_investments_details(ItemElement):
        klass = Investment

        obj_id = Env("id")
        obj_quantity = CleanDecimal.French(CleanText('//span[contains(text(), "part")]'))
        obj_valuation = CleanDecimal.French(CleanText('//span[contains(text(), "valorisation")]'))
        obj__init_valuation = CleanDecimal.French(CleanText('//i[contains(text(), "Valeur initiale")]'))

        def obj_unitprice(self):
            return Field("_init_valuation")(self) / Field("quantity")(self)

        def obj_unitvalue(self):
            return Field("valuation")(self) / Field("quantity")(self)

        def obj_diff(self):
            return Field("_init_valuation")(self) - Field("valuation")(self)

        def obj_diff_ratio(self):
            return Field("valuation")(self) / Field("_init_valuation")(self)
