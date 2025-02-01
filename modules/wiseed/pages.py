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

# flake8: compatible

from decimal import Decimal

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanText, Coalesce, Date, Eval, Format, Regexp
from woob.browser.pages import JsonPage, LoggedPage, RawPage
from woob.capabilities.address import PostalAddress
from woob.capabilities.bank import Account
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.base import NotAvailable
from woob.capabilities.profile import Person
from woob.tools.capabilities.bank.investments import create_french_liquidity


def float_to_decimal(f):
    return Decimal(str(f))


class WebsiteKeyPage(RawPage):
    def get_website_key(self):
        # the website key is present between js variables defined in this file
        return Regexp(pattern=r'\[.{1},.{1},.{1},"([^"].+)",.{1},.{1},\(\)=>{grecaptcha\.execute').filter(
            self.doc.decode("utf-8")
        )


class WalletPage(LoggedPage, JsonPage):
    def get_liquidities(self):
        value = float_to_decimal(Dict("solde")(self.doc))
        return create_french_liquidity(value)


class ProfilePage(LoggedPage, JsonPage):
    def get_wallet_status(self):
        return Dict("statuts/walletOk")(self.doc)

    @method
    class get_account(ItemElement):
        klass = Account

        obj_id = "_wiseed_"
        obj_type = Account.TYPE_CROWDLENDING
        obj_number = CleanText(Dict("id"))
        obj_label = "WiSEED"
        obj_currency = "EUR"

    @method
    class get_profile(ItemElement):
        klass = Person

        obj_email = Dict("email")
        # On freshly created accounts, 'identite/dateNaissance' may not exist.
        obj_birth_date = Date(
            CleanText(Dict("identite/dateNaissance", default=None), default=NotAvailable), default=NotAvailable
        )
        obj_firstname = CleanText(Dict("identite/prenom"))
        obj_lastname = CleanText(Dict("identite/nomDeNaissance"))
        obj_nationality = Dict("identite/nationalite", default=NotAvailable)

        class obj_postal_address(ItemElement):
            klass = PostalAddress

            # "adresseDeCorrespondance" might be empty, use "adresseFiscale" instead
            obj_street = Coalesce(
                CleanText(Dict("coordonnees/adresseDeCorrespondance/adresse"), default=NotAvailable),
                CleanText(Dict("coordonnees/adresseFiscale/adresse"), default=NotAvailable),
                default=NotAvailable,
            )
            obj_city = Coalesce(
                CleanText(Dict("coordonnees/adresseDeCorrespondance/ville"), default=NotAvailable),
                CleanText(Dict("coordonnees/adresseFiscale/ville"), default=NotAvailable),
                default=NotAvailable,
            )
            obj_postal_code = Coalesce(
                CleanText(Dict("coordonnees/adresseDeCorrespondance/codePostal"), default=NotAvailable),
                CleanText(Dict("coordonnees/adresseFiscale/codePostal"), default=NotAvailable),
                default=NotAvailable,
            )
            obj_country = Coalesce(
                CleanText(Dict("coordonnees/adresseDeCorrespondance/pays"), default=NotAvailable),
                CleanText(Dict("coordonnees/adresseFiscale/pays"), default=NotAvailable),
                default=NotAvailable,
            )


class BaseInvestElement(ItemElement):
    klass = Investment
    # There is another id (cibleId) but it's not unique.
    # The PSU can invest at different time on the same
    # stock and we must not aggregate them to match website display
    obj_id = Format("%s_%s", Dict("operationId"), Dict("cibleId"))

    obj_label = Format(
        "%s (%s)",
        CleanText(Dict("operationNom")),
        CleanText(Dict("cibleNom")),
    )

    obj_valuation = Eval(float_to_decimal, Dict("montantInvesti"))


class InvestmentsPage(LoggedPage, JsonPage):
    def get_invest_list(self, invest_type):
        return Dict(invest_type, default=None)(self.doc)

    @method
    class iter_stocks(DictElement):
        item_xpath = "actions"

        class item(BaseInvestElement):
            obj_diff_ratio = Eval(float_to_decimal, Dict("coeffPerformanceIntermediaire"))

    @method
    class iter_bonds(DictElement):
        item_xpath = "obligations"

        class item(BaseInvestElement):
            pass

    @method
    class iter_equities(DictElement):
        item_xpath = "titresParticipatifs"

        class item(BaseInvestElement):
            pass
