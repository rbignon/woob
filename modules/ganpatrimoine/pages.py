# Copyright(C) 2012-2019  Budget Insight
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
from decimal import Decimal

from woob.browser.elements import DictElement, ItemElement, ListElement, TableElement, method
from woob.browser.filters.html import Attr, HasElement, Link, TableCell
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    CleanDecimal,
    CleanText,
    Coalesce,
    Currency,
    Date,
    Env,
    Eval,
    Field,
    Format,
    FromTimestamp,
    Lower,
    Map,
    MapIn,
    Regexp,
)
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, pagination
from woob.capabilities.bank import Account
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.base import NotAvailable, empty
from woob.capabilities.profile import Person
from woob.tools.capabilities.bank.investments import IsinCode, IsinType
from woob.tools.capabilities.bank.transactions import FrenchTransaction
from woob.tools.date import parse_french_date


def float_to_decimal(f):
    if empty(f):
        return NotAvailable
    return Decimal(str(f))


class RootPage(HTMLPage):
    def is_website_unavailable(self):
        return HasElement('//head/title[text()="Site temporairement indisponible"]')(self.doc)


class LoginPage(HTMLPage):
    def get_vk_password(self, password):
        # The virtual keyboard is a table with cells containing the VK's
        # displayed number and JS code with the transformed number
        # <td id="hoverable" class="hoverable" onclick="appendTextInputCalculator(0, 'password')" >5</td>

        vk_dict = {}
        for vk_cell in self.doc.xpath('//table[@id="calculator"]//td'):
            vk_dict[CleanText(".")(vk_cell)] = Regexp(Attr(".", "onclick"), r"\((\d), 'password'\)")(vk_cell)
        return "".join(vk_dict[char] for char in password)

    def login(self, username, password):
        form = self.get_form()
        form["username"] = username
        form["password"] = self.get_vk_password(password)
        form.submit()

    def has_strong_authentication(self):
        return CleanText('//h4[contains(text(), "Connexion sécurisée par SMS")]')(self.doc)

    def get_otp_phone_number(self):
        return CleanText("//form//b")(self.doc)

    def get_otp_message(self):
        return CleanText("//form/div[2]")(self.doc)

    def get_error_message(self):
        return CleanText('//div[@id="modal"]//div[@class="gpm-modal-header"]')(self.doc)

    def is_wrongpass(self):
        error = CleanText('//div[@id="modal"]//div[@class="gpm-modal-body"]')(self.doc)
        return "identifiant ou mot de passe est incorrect" in error

    def post_2fa_form(self, otp):
        form = self.get_form(id="kc-form-login")
        form["otpCode"] = otp
        form.submit()


class HomePage(LoggedPage, HTMLPage):
    pass


class Transaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r"^(VIR DE|Vir à|Virement) (?P<text>.*)"), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r"^Versement (?P<text>.*)"), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r"^CHEQUE"), FrenchTransaction.TYPE_CHECK),
        (re.compile(r"^(Prl de|Prlv) (?P<text>.*)"), FrenchTransaction.TYPE_ORDER),
        (re.compile(r"^(Ech.|Echéance) (?P<text>.*)"), FrenchTransaction.TYPE_LOAN_PAYMENT),
        (re.compile(r"^Regl Impayé prêt"), FrenchTransaction.TYPE_LOAN_PAYMENT),
        (re.compile(r"^Frais tenue de compte"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(Cotis|Cotisation) (?P<text>.*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(Int |Intérêts)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^Régularisation"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^Prélèvement"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^Commission"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^Facture (?P<dd>\d{2})/(?P<mm>\d{2}) - (?P<text>.*)"), FrenchTransaction.TYPE_CARD),
        (re.compile(r"(?P<dd>\d{2})/(?P<mm>\d{2}) - (?P<text>.*) Paiement carte"), FrenchTransaction.TYPE_CARD),
        (re.compile(r"(?P<dd>\d{2})/(?P<mm>\d{2}) - (?P<text>.*) Retrait carte"), FrenchTransaction.TYPE_WITHDRAWAL),
        (re.compile(r"(?P<dd>\d{2})/(?P<mm>\d{2}) - (?P<text>.*) Rembt carte"), FrenchTransaction.TYPE_PAYBACK),
    ]


ACCOUNT_TYPES = {
    "compte bancaire": Account.TYPE_CHECKING,
    "epargne bancaire": Account.TYPE_SAVINGS,
    "crédit": Account.TYPE_LOAN,
    "epargne": Account.TYPE_LIFE_INSURANCE,
    "objectif retraite": Account.TYPE_LIFE_INSURANCE,
    "retraite active": Account.TYPE_LIFE_INSURANCE,
    "patrimoine evolution": Account.TYPE_LIFE_INSURANCE,
    "libregan": Account.TYPE_LIFE_INSURANCE,
    "groupama epargne": Account.TYPE_LIFE_INSURANCE,
    "groupama modulation": Account.TYPE_LIFE_INSURANCE,
    "chromatys": Account.TYPE_LIFE_INSURANCE,
    "gan retraite": Account.TYPE_LIFE_INSURANCE,
    "nouvelle vie": Account.TYPE_PER,
    "retraite collective": Account.TYPE_PER,
    "perp": Account.TYPE_PERP,
    "pee": Account.TYPE_PEE,
    "madelin": Account.TYPE_MADELIN,
    "retraite pro": Account.TYPE_MADELIN,
    "compte titres": Account.TYPE_MARKET,
    "certificat mutualiste": Account.TYPE_MARKET,
}


class AccountsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):

        class item(ItemElement):
            klass = Account

            def condition(self):
                # Skip insurances, accounts that are cancelled or replaced,
                # and accounts that have no available detail.
                # Sometimes the key for 'produit/format' is not present,
                # skip the account anyway if it's the case since it's not displayed on the website.
                if Dict("resilie")(self) or Dict("remplace")(self) or not Dict("produit/format", default=None)(self):
                    return False
                return True

            obj_id = obj_number = CleanText(Dict("identifiant"))
            obj_label = CleanText(Dict("produit/libelle"))
            obj_opening_date = FromTimestamp((Dict("dateEffet")), millis=True)
            obj__product_code = CleanText(Dict("produit/code"))
            obj_type = MapIn(Lower(Field("label")), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)
            obj__category = Lower(Dict("produit/famille"))
            obj__investments = []

            def obj__url(self):
                url = Dict("debranchement/url", default=NotAvailable)(self)
                if not url:
                    return "/redirect/igc/" + Field("id")(self)


class AccountDetailsPage(LoggedPage, JsonPage):
    def has_investments(self):
        return HasElement(Dict("contrat/listeSupports", default=NotAvailable))(self.doc)

    @method
    class fill_account(ItemElement):
        obj_balance = CleanDecimal.US(
            Format("%s%s", Dict("contrat/signeSolde"), Eval(float_to_decimal, Dict("contrat/solde")))
        )
        obj_currency = Currency(Dict("contrat/devise"))

    @method
    class fill_loan(ItemElement):
        obj_balance = Eval(lambda x: float_to_decimal(-x), Dict("contrat/solde"))
        obj_currency = Currency(Dict("contrat/devise"))

    @method
    class fill_wealth_account(ItemElement):
        # Depending on the status/type of account, balances may not be available. It will be skipped later on if
        # no balance can be found after checking all ressources.
        obj_balance = Coalesce(
            Eval(float_to_decimal, Dict("contrat/montant", default=NotAvailable)),  # Needed for some life insurances
            Eval(float_to_decimal, Dict("contrat/montantEpargneContrat", default=NotAvailable)),
            default=NotAvailable,
        )
        obj_currency = "EUR"
        # The valuation_diff_ratio is already divided by 100
        obj_valuation_diff_ratio = Eval(float_to_decimal, Dict("contrat/pourcentagePerformanceContrat", default=None))
        obj_iban = CleanText(Dict("listeRib/0/iban", default=None), default=NotAvailable)

    @method
    class iter_cards(DictElement):
        item_xpath = "contrat/listeCartes"

        class item(ItemElement):
            klass = Account

            def condition(self):
                # Keep only deferred card with available details
                return Dict("nature")(self) == "DIFFERE" and isinstance(Dict("montant", default=None)(self), float)

            obj_id = obj_number = Dict("numero")
            obj_label = Format("%s %s", CleanText(Dict("libelle")), CleanText(Dict("numero")))
            obj_currency = Currency(Dict("devise"))
            obj_type = Account.TYPE_CARD
            obj__category = "Carte"
            obj_balance = Decimal(0)
            obj_coming = CleanDecimal.US(Format("%s%s", Dict("signe"), Eval(float_to_decimal, Dict("montant"))))
            obj__url = NotAvailable
            obj__investments = []

    @method
    class iter_investments(DictElement):
        item_xpath = "contrat/listeSupports"

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(Dict("libelleSupport"))
            obj_valuation = Eval(float_to_decimal, Dict("montantSupport"))
            obj_quantity = Eval(float_to_decimal, Dict("nbUniteCompte", default=None))
            obj_unitvalue = Eval(float_to_decimal, Dict("valeurUniteCompte", default=None))
            obj_portfolio_share = Eval(lambda x: float_to_decimal(x) / 100, Dict("tauxSupport", default=None))
            obj_code = IsinCode(Dict("codeISIN", default=None), default=NotAvailable)
            obj_code_type = IsinType(Dict("codeISIN", default=None))
            obj_asset_category = CleanText(Dict("classeActif/libelle", default=None))
            # Note: recommended_period & srri are not available on this website

            def obj_performance_history(self):
                perfs = {}
                if Dict("detailPerformance/perfSupportUnAn", default=None)(self):
                    perfs[1] = Eval(lambda x: float_to_decimal(x) / 100, Dict("detailPerformance/perfSupportUnAn"))(
                        self
                    )
                if Dict("detailPerformance/perfSupportTroisAns", default=None)(self):
                    perfs[3] = Eval(lambda x: float_to_decimal(x) / 100, Dict("detailPerformance/perfSupportTroisAns"))(
                        self
                    )
                if Dict("detailPerformance/perfSupportCinqAns", default=None)(self):
                    perfs[5] = Eval(lambda x: float_to_decimal(x) / 100, Dict("detailPerformance/perfSupportCinqAns"))(
                        self
                    )
                return perfs


class AccountDetailsPageBis(LoggedPage, JsonPage):
    @method
    class fill_wealth_account(ItemElement):
        # Depending on the status/type of account, balances may not be available. It will be skipped later on if
        # no balance can be found after checking all ressources.
        obj_balance = CleanDecimal.SI(Dict("contrat/montantEpargneAcquise", default=None), default=NotAvailable)
        obj_currency = "EUR"


class HistoryPage(LoggedPage, JsonPage):
    @method
    class iter_wealth_history(DictElement):
        item_xpath = "*/historiques"

        class item(ItemElement):
            klass = Transaction

            obj_label = CleanText(Dict("libelle"))
            # There is only one date for each transaction
            obj_date = obj_rdate = FromTimestamp(Dict("date"), millis=True)
            obj_type = Transaction.TYPE_BANK

            def obj_amount(self):
                amount = Eval(float_to_decimal, Dict("montant"))(self)
                if Dict("negatif")(self):
                    return -amount
                return amount


GENDERS = {"FEMME": "Female", "HOMME": "Male", NotAvailable: NotAvailable}


class ProfilePage(LoggedPage, JsonPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_name = Dict("identite")
        obj_firstname = Dict("prenom")
        obj_lastname = Dict("nom")
        obj_family_situation = Dict("statutFamilial")
        obj_gender = Map(Dict("sexe", default=NotAvailable), GENDERS)
        obj_birth_date = FromTimestamp(Dict("dateNaissance"), millis=True)


## Bank /wps/myportal/ html sub pages - Used by child modules ##


WPS_ACCOUNT_TYPES = {
    "comptes bancaires": Account.TYPE_CHECKING,
    "epargne bancaire": Account.TYPE_SAVINGS,
    "crédits": Account.TYPE_LOAN,
    "assurance vie": Account.TYPE_LIFE_INSURANCE,
    "certificats mutualistes": Account.TYPE_MARKET,
}


class WPSAccountsPage(LoggedPage, HTMLPage):
    def get_account_history_url(self, account_id):
        return Regexp(Attr('//a[contains(text(), "%s")]' % account_id, "onclick"), r"'(.*)'")(self.doc)

    @method
    class iter_accounts(ListElement):
        item_xpath = '//form/table[@class="ecli"]'

        class iter_items(ListElement):
            # Note: through web browser, we can see a "tbody" between the table and tr
            # but it does not exist inside the source file.
            item_xpath = 'tr[not(@class="entete")]'

            def parse(self, el):
                category_title = CleanText('tr[@class="entete"]/th[has-class("nom_compte")]')(self)
                self.env["category_title"] = category_title

            class item(ItemElement):
                klass = Account

                obj__raw_label = CleanText('./td[has-class("cel1")]/a', symbols="•")
                # No IBAN available for now

                obj_iban = NotAvailable
                obj_label = Regexp(Field("_raw_label"), r"^(.*) N°")
                obj_id = Regexp(Field("_raw_label"), r"N° ([\dA-Z]+)")
                obj_number = Field("id")
                obj_balance = CleanDecimal.French('./td[@class="cel3"]', default=NotAvailable)
                obj_currency = Currency('./td[@class="cel3"]')
                obj__investments = []

                def obj_type(self):
                    if HasElement('./td[@class="cel1 decal"]')(self):
                        return Account.TYPE_CARD
                    return MapIn(Lower(Env("category_title")), WPS_ACCOUNT_TYPES)(self)

                obj__history_url = Regexp(
                    Attr("./td/a", "onclick", default=NotAvailable), r"'(.*)'", default=NotAvailable
                )


class RibPage(LoggedPage, HTMLPage):
    @method
    class fill_account(ItemElement):
        obj_iban = Regexp(
            CleanText('//div/table/tr[1]/td[1]//li[contains(., "IBAN")]', replace=[(" ", "")], default=NotAvailable),
            "IBAN:(.*)",
            default=NotAvailable,
        )


class WPSPortalPage(LoggedPage, HTMLPage):
    def get_account_rib_url(self, account_id):
        src_url = Regexp(
            Attr('//div[@class="action_context"]/a[@class="rib"]', "onclick", default=NotAvailable),
            r"'(/wps/myportal/.*/id=QCPDetailRib.jsp/c=cacheLevelPage/=/)'",
            default=NotAvailable,
        )(self.doc)
        if src_url == NotAvailable:
            return None
        return f"{src_url}?paramNumCpt={account_id}"

    @pagination
    @method
    class iter_history(TableElement):
        item_xpath = '//table[@id="releve_operation"]//tr[td]'
        head_xpath = '//table[@id="releve_operation"]//tr/th'

        col_label = "Libellé"
        col_date = ["Date opé", "Date d'opé"]
        col_debit = "Débit"
        col_credit = "Crédit"

        def next_page(self):
            js_link = Attr('//div[@id="pagination"]/a[@class="suivon"]', "onclick", default=NotAvailable)
            next_link = Regexp(js_link, r"'(.*)'", default=False)(self)
            if next_link:
                next_number_page = Regexp(js_link, r"', (\d+)\)")(self)
                data = {
                    "numCompte": Env("account_id")(self),
                    "vue": "ReleveOperations",
                    "tri": "DateOperation",
                    "sens": "DESC",
                    "page": next_number_page,
                    "nb_element": "25",
                }
                page = self.page.browser.location(next_link, data=data).page
                return page

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                return len(self.el.xpath("./td")) > 2

            obj_date = Date(CleanText(TableCell("date")), dayfirst=True)
            obj_rdate = Date(
                Regexp(CleanText(TableCell("label", colspan=True)), r"(\d+/\d+/\d+)", default=""),
                dayfirst=True,
                default=NotAvailable,
            )
            obj_raw = Transaction.Raw(CleanText(TableCell("label")))

            def obj_amount(self):
                # For only a few accounts, the "debit" values are negatives
                # Ex.: OPTION ASTREA PLUS - CSL
                return CleanDecimal.French(TableCell("credit"), default=0)(self) - CleanDecimal.French(
                    TableCell("debit"), sign="+", default=0
                )(self)

    @method
    class iter_card_history(TableElement):
        item_xpath = '//table[@id="releve_operation"]//tr[td]'
        head_xpath = '//table[@id="releve_operation"]//tr/th'

        col_label = "Libellé"
        col_date = "Date"
        col_amount = "Montant"

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                return len(self.el.xpath("./td")) > 2

            obj_label = CleanText(TableCell("label"))
            obj_rdate = Date(CleanText(TableCell("date")), dayfirst=True)
            obj_amount = CleanDecimal.French(TableCell("amount"), sign="-")
            obj_type = Transaction.TYPE_CARD
            obj_date = Date(
                Regexp(CleanText('//div[@class="entete1_bloc"]/p[contains(text(), "Débité le")]'), r"Débité le (.+) :"),
                parse_func=parse_french_date,
            )

    @method
    class iter_wealth_history(TableElement):
        item_xpath = '//table[@id="releve_operation"]//tr[td]'
        head_xpath = '//table[@id="releve_operation"]//tr/th'

        col_date = "Date opération"
        col_label = "Opération"
        col_amount = "Valeur"

        class item(ItemElement):
            klass = Transaction

            obj_date = obj_rdate = Date(CleanText(TableCell("date")), dayfirst=True)
            obj_label = CleanText(TableCell("label"))
            obj_amount = CleanDecimal.French(TableCell("amount"))
            obj_type = Transaction.TYPE_BANK


FORM_KEYS = [
    "ctl00$ctl00$ctl05",
    "ctl05_TSM",
    "__EVENTTARGET",
    "__EVENTARGUMENT",
    "__VIEWSTATE",
    "__VIEWSTATEGENERATOR",
    "__SCROLLPOSITIONX",
    "__SCROLLPOSITIONY",
    "__VIEWSTATEENCRYPTED",
    "__EVENTVALIDATION",
    "__ASYNCPOST",
    "RadAJAXControlID",
]


def generate_form(panel):
    return {
        "ctl00$ctl00$ctl05": f"ctl00$ctl00$cphBody$cphBody$ctl00$ctl00$cphBody$cphBody$AjaxPanelPanel|ctl00$ctl00$cphBody$cphBody${panel}",
        "__EVENTTARGET": f"ctl00$ctl00$cphBody$cphBody${panel}",
        "__EVENTARGUMENT": "undefined",
        "__ASYNCPOST": "true",
        "RadAJAXControlID": f"ctl00_ctl00_cphBody_cphBody_{panel}",
    }


class LifeInsurancePage(LoggedPage, HTMLPage):
    def load_data(self):
        form = self.get_form(id="form1")

        # We need to remove the key from the form that are not used on the website
        for key in list(form.keys()):
            if key not in FORM_KEYS:
                form.pop(key)

        form.update(generate_form("AjaxPanel"))
        form.submit()

    def get_details_url(self):
        return Link('//a[contains(@id,"DetailsEpargne")]')(self.doc)

    @method
    class fill_account(ItemElement):
        obj_balance = CleanDecimal.French('//span[@id="cphBody_cphBody_lblMontantEpargne"]')
        obj_valuation_diff = CleanDecimal.French('//span[@id="cphBody_cphBody_lblMontantPMValue"]')


class LifeInsurancePageInvestmentsDetails(LoggedPage, HTMLPage):
    def load_details(self):
        form = self.get_form(id="form1")

        # We need to remove the key from the form that are not used on the website
        for key in list(form.keys()):
            if key not in FORM_KEYS:
                form.pop(key)

        form.update(generate_form("AjaxPanel_Epargne"))
        form.submit()

    @method
    class fill_account(ItemElement):
        def obj_valuation_diff_ratio(self):
            valuation_diff_ratio = CleanDecimal.French(
                CleanText('//h5[@id="cphBody_cphBody_ucEpargneChart_ctlTauxPerformance"]'), default=NotAvailable
            )(self)

            if not empty(valuation_diff_ratio):
                return valuation_diff_ratio / 100
            return NotAvailable

    @method
    class iter_investments(TableElement):
        head_xpath = '//div[contains(@id, "pnlEpargneSupports")]//table/thead//th'
        item_xpath = '//div[contains(@id, "pnlEpargneSupports")]//table/tbody//tr'

        col_label = "Fonds financiers"
        col_quantity = "Nb UC"
        col_unitvalue = "Valeur UC"
        col_vdate = "Date valeur UC"
        col_valuation = "Montant épargne"
        col_portfolio_share = "Répartition"

        class item(ItemElement):
            klass = Investment

            def condition(self):
                return CleanDecimal.French(TableCell("valuation"))(self)

            obj_label = CleanText(TableCell("label"))
            obj_quantity = CleanDecimal.French(TableCell("quantity"), default=NotAvailable)
            obj_unitvalue = CleanDecimal.French(TableCell("unitvalue"), default=NotAvailable)
            obj_valuation = CleanDecimal.French(TableCell("valuation"))
            obj_vdate = Date(CleanText(TableCell("vdate")), dayfirst=True, default=NotAvailable)

            def obj_portfolio_share(self):
                portfolio_share = CleanDecimal.French(TableCell("portfolio_share"), default=NotAvailable)(self)

                if not empty(portfolio_share):
                    return portfolio_share / 100
                return NotAvailable
