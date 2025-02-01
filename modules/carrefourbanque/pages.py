# Copyright(C) 2013 Romain Bignon
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

import base64
import datetime
import re
from io import BytesIO

from PIL import Image

from woob.browser.elements import DictElement, ItemElement, ListElement, TableElement, method
from woob.browser.filters.html import Attr, AttributeNotFound, Link, TableCell, XPathNotFound
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, CleanText, Coalesce, Currency, Date, Eval, Field, Regexp
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, pagination
from woob.capabilities.bank import Account
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.base import NotAvailable, empty
from woob.tools.capabilities.bank.transactions import FrenchTransaction


class CarrefourBanqueKeyboard:
    symbols = {
        "0": "11100000001111100000000011100000000000110000010000010000011100001000001110000000001111000000000111100000000011111000000001111100000000111100000000011111000000001111000000000111100000000001110000000000111000011000001000001100000000001111000000000111110000000111",
        "1": "11111110001111111110000111111110000011111110000001111100000000111110000000011111000000001111100010000111110011000011111111100001111111110000111111111000011111111100001111111110000111111111000011111111100001111111110000111111111000011111111100001111111111111111",
        "2": "11000000011111000000000011000000000001100001110000011011111100001111111110000111111111000011111111100011111111100001111111100001111111100000111111100000111111100000111111100000111111110000111111110000111111110000000000001000000000000100000000000011111111111111",
        "3": "11000000001110000000000011000000000000110011111000011111111100001111111110000111111111000111111110000011110000000011111000000001111110000000011111111110000111111111000011111111110001111111110000101111111000010000000000001000000000001100000000001111111111111111",
        "4": "11111110000011111111000001111111000000111111000000011111000000001111100010000111100001000011100001100001100001110000110001111000010000111100001000111110000100000000000000000000000000000000000000011111111000011111111100001111111110000111111111000011111111111111",
        "5": "10000000000111000000000011100000000001110001111111110000111111111000011111111100001111111110000000000111000000000001100000000000011111111000001111111110000111111111100011111111110001111111110000101111110000010000000000011000000000001100000000011111111111111111",
        "6": "11110000000111110000000011110000000001110000011111111000111111111000011111111100001111111110001000000111000000000001100000000000010000011100001000011111000100011111100010000111110001000011111000100001111000011000000000011110000000001111100000011111111111111111",
        "7": "00000000000000000000000000000000000000011111111100001111111100001111111110000111111111000011111111000011111111100001111111100001111111110000111111110000111111111000011111111000011111111100001111111100000111111110000111111110000011111111000011111111111101111111",
        "8": "11100000001111000000000001100000000000100001111100000000111110000000011111000010000111000011000000000001110000000011111000000000111000000000001000001100000000001111100000001111111000000011111100000001111100000000000000000100000000000111000000000111111111111111",
        "9": "11100000001111000000000011100000000000100001111000000000111110000000111111000000011111100000000111110000000011110000000000000000001000000000000110000000100011111111100001111111110000111111110000111111110000011000000000011100000000011110000000111111111111111111",
    }

    def __init__(self, data_code):
        self.fingerprints = {}

        for code, data in data_code.items():
            img = Image.open(BytesIO(data))
            img = img.convert("RGB")
            matrix = img.load()
            s = ""
            # The digit is only displayed in the center of image
            for y in range(15, 35):
                for x in range(19, 32):
                    (r, g, b) = matrix[x, y]
                    # If the pixel is "white" enough
                    if r + g + b > 700:
                        s += "1"
                    else:
                        s += "0"

            self.fingerprints[code] = s

    def get_symbol_code(self, digit):
        fingerprint = self.symbols[digit]
        for code, string in self.fingerprints.items():
            if string == fingerprint:
                return code
        # Image contains some noise, and the match is not always perfect
        # (this is why we can't use md5 hashs)
        # But if we can't find the perfect one, we can take the best one
        best = 0
        result = None
        for code, string in self.fingerprints.items():
            match = 0
            for j, bit in enumerate(string):
                if bit == fingerprint[j]:
                    match += 1
            if match > best:
                best = match
                result = code
        return result

    def get_string_code(self, string):
        code = ""
        for c in string:
            code += self.get_symbol_code(c) + "-"
        return code


def MyDecimal(*args, **kwargs):
    kwargs.update(replace_dots=True, default=NotAvailable)
    return CleanDecimal(*args, **kwargs)


class LoginPage(HTMLPage):
    def build_doc(self, data):
        # allow_redirects must be set to false for the password form submit
        # so that SCA can be detected ahead. That makes lxml crash because
        # some redirections are totally blank page
        if not len(data):
            data = b"<html></html>"
        return super().build_doc(data)

    def on_load(self):
        """
        website may have identify us as a robot, if it happens login form won't be available in login page
        and there will be nothing on body except a meta tag with robot name
        """
        try:
            attr = Attr("head/meta", "name")(self.doc)
        except (AttributeNotFound, XPathNotFound):  # XPathNotFound for blank pages cases
            # website have identify us as a human ;)
            return

        # sometimes robots is uppercase and there is an iframe
        # sometimes it's lowercase and there is a script
        if attr == "ROBOTS":
            self.browser.location(Attr("//iframe", "src")(self.doc))
        elif attr == "robots":
            self.browser.location(Attr("//script", "src")(self.doc))

    def enter_login(self, username):
        form = self.get_form(nr=1)
        form["name"] = username
        form["op"] = "Valider"
        form["cpass"] = ""
        form.pop("form_number")
        form.submit()

    def get_message_if_old_login(self):
        return CleanText('//div[contains(@class, "alert")]', children=False)(self.doc)

    def get_error_message(self):
        return CleanText('//div[contains(@class, "alert")]')(self.doc)

    def enter_password(self, password):
        data_code = {}
        for img in self.doc.xpath('//img[@class="digit"]'):
            data_code[img.attrib["data-code"]] = base64.b64decode(re.search(r"base64,(.*)", img.attrib["src"]).group(1))
        codestring = CarrefourBanqueKeyboard(data_code).get_string_code(password)

        form = self.get_form(nr=1)
        form["pass"] = "*" * len(password)
        form["cpass"] = codestring
        form["op"] = "Me+connecter"
        form.pop("form_number")  # don't remember me

        form.submit(allow_redirects=False)

    def get_dsp2_auth_code(self):
        return Regexp(
            CleanText('//script[contains(text(), "popin_dsp2")]', replace=[("-", "_")]),
            r'"popin_dsp2":"(\w+)"',
            default="",
        )(self.doc)


class KYCPage(HTMLPage):
    def get_error_message(self):
        return CleanText(
            '//form[contains(@id, "user-login-enrollment-details-verify-form")]'
            + '//section[contains(@class, "outerdiv")]//p'
        )(self.doc)


class MaintenancePage(HTMLPage):
    def get_message(self):
        return CleanText('//div[@class="bloc-title"]/h1//div[has-class("field-item")]')(self.doc)


class IncapsulaResourcePage(HTMLPage):
    def __init__(self, *args, **kwargs):
        # this page can be a html page, or just javascript
        super().__init__(*args, **kwargs)
        self.is_javascript = None

    def on_load(self):
        self.is_javascript = "html" not in CleanText("*")(self.doc)

    def get_recaptcha_site_key(self):
        return Attr('//div[@class="g-recaptcha"]', "data-sitekey")(self.doc)


class Transaction(FrenchTransaction):
    PATTERNS = [(re.compile(r"^(?P<text>.*?) (?P<dd>\d{2})/(?P<mm>\d{2})$"), FrenchTransaction.TYPE_CARD)]


class item_account_generic(ItemElement):
    """Generic accounts properties for Carrefour homepage"""

    klass = Account

    def obj_balance(self):
        balance = CleanDecimal.French('.//div[@class="catre_col_one"]/h3')(self)
        if Field("type")(self) in (Account.TYPE_LOAN,):
            return -balance
        return balance

    obj_currency = Currency('.//div[@class="catre_col_one"]/h3')
    obj_label = CleanText('.//div[@class="right_col_wrapper"]/h2')
    obj_id = Regexp(CleanText('.//p[contains(text(), "N°")]'), r"N°\s+(\d+)")
    obj_number = Field("id")

    def obj_url(self):
        acc_number = Field("id")(self)
        xpath_link = f'//li[contains(., "{acc_number}")]/ul/li/a'
        return Link(xpath_link)(self)


class iter_history_generic(Transaction.TransactionsElement):
    head_xpath = '//div[*[contains(text(), "opérations")]]/table//thead/tr/th'
    item_xpath = '//div[*[contains(text(), "opérations")]]/table/tbody/tr[td]'

    col_debittype = "Mode"

    def next_page(self):
        next_page = Link('//a[contains(text(), "précédentes")]', default=None)(self)
        if next_page:
            return "/%s" % next_page

    class item(Transaction.TransactionElement):
        def obj_type(self):
            if len(self.el.xpath("./td")) <= 3:
                return Transaction.TYPE_BANK
            col = TableCell("debittype", default=None)
            if col(self):
                debittype = CleanText(col)(self)
                if debittype == "Différé":
                    return Transaction.TYPE_DEFERRED_CARD
            return Transaction.TYPE_CARD

        def condition(self):
            return TableCell("raw")(self)


class HomePage(LoggedPage, HTMLPage):
    @method
    class iter_loan_accounts(ListElement):  # Prêts
        item_xpath = '//div[@class="pp_espace_client"]'

        class item(item_account_generic):
            obj_type = Account.TYPE_LOAN
            obj_label = CleanText('.//div[@class="block_pret block_synthproduct"]/h2')
            obj_id = Regexp(CleanText('.//p[contains(text(), "Réf. dossier")]'), r"Réf. dossier :\s+(\d+)")
            obj_currency = Currency('.//span[contains(., "Restants à rembourser")]//following-sibling::span')

            obj_balance = CleanDecimal.French(
                './/span[contains(., "Restants à rembourser")]//following-sibling::span', sign="-"
            )

    @method
    class iter_card_accounts(ListElement):  # PASS cards
        item_xpath = '//div[div[contains(./h2, "Carte et Crédit") and contains(./p, "N°")]]'

        class item(item_account_generic):
            obj_type = Account.TYPE_CARD
            obj_label = CleanText('.//div[@class="block_cartepass block_synthproduct"]/h2')
            obj_currency = Coalesce(
                Currency('.//p[contains(., "encours depuis le")]//preceding-sibling::h3'),
                Currency('.//span[contains(., "Plafond")]//following-sibling::span'),
                Currency('.//span[contains(., "Disponible à crédit")]//following-sibling::span'),
            )

            def obj_balance(self):
                available = CleanDecimal.French(
                    './/p[contains(., "encours depuis le")]//preceding-sibling::h3',
                    default=NotAvailable,
                )(self)
                if available:
                    return -available

                # No "en cours" available: return - (total_amount - available_amount)
                total_amount = CleanDecimal.French(
                    './/span[contains(., "Plafond")]//following-sibling::span',
                    default=NotAvailable,
                )(self)

                available_amount = CleanDecimal.French(
                    './/span[contains(., "Disponible à crédit")]//following-sibling::span',
                    default=NotAvailable,
                )(self)

                if empty(total_amount) or empty(available_amount):
                    return NotAvailable
                return -(total_amount - available_amount)

    @method
    class iter_saving_accounts(ListElement):  # livrets
        item_xpath = (
            '//div[div[(contains(./h2, "Livret Carrefour") or contains(./h2, "Epargne")) and contains(./p, "N°")]]'
        )

        class item(item_account_generic):
            obj_type = Account.TYPE_SAVINGS
            obj_label = Coalesce(
                CleanText('.//div[@class="right_col_wrapper"]/h2'),
                CleanText('.//div[@class="block_compteproduct block_synthproduct"]/h2'),
            )
            obj_url = Coalesce(
                Link('.//a[contains(., "Historique des opérations")]', default=NotAvailable),
                Link('..//div//a[contains(., "Historique des opérations")]', default=NotAvailable),
            )
            obj_currency = Currency('.//span[contains(., "Montant")]//following-sibling::span')

            def obj_balance(self):
                val = CleanDecimal.French(
                    './/span[contains(., "Montant")]//following-sibling::span', default=NotAvailable
                )(self)
                if val is not NotAvailable:
                    return val
                val = CleanDecimal.French(
                    Regexp(CleanText('.//div[@class="catre_col_one"]/h3'), r"([\d ,]+€)"),
                )(self)
                return val

    @method
    class iter_life_accounts(ListElement):  # Assurances vie
        item_xpath = '//div[div[(contains(./h2, "Carrefour Horizons") or contains(./h2, "Carrefour Avenir")) and contains(./p, "N°")]]'

        class item(item_account_generic):
            obj_type = Account.TYPE_LIFE_INSURANCE
            obj_label = CleanText('.//div[@class="block_compteproduct block_synthproduct"]/h2')
            obj_balance = CleanDecimal.French('.//span[contains(., "Montant")]//following-sibling::span')
            obj_currency = Currency('.//span[contains(., "Montant")]//following-sibling::span')

            def obj_url(self):
                acc_number = Field("id")(self)
                xpath_link = ('//li[contains(., "{acc_number}")]/ul/li/a[contains(text(), "opérations")]').format(
                    acc_number=acc_number
                )
                return Link(xpath_link)(self)

            def obj__life_investments(self):
                xpath_link = '//li[contains(., "{acc_number}")]/ul/li/a[contains(text(), "Solde")]'.format(
                    acc_number=Field("id")(self)
                )
                return Link(xpath_link)(self)


class TransactionsPage(LoggedPage, HTMLPage):
    @pagination
    @method
    class iter_history(iter_history_generic):
        head_xpath = '//table[@id="creditHistory" or @id="TransactionHistory"]/thead/tr/th'
        item_xpath = '//table[@id="creditHistory" or @id="TransactionHistory"]/tbody/tr[td]'


class SavingHistoryPage(LoggedPage, HTMLPage):
    @pagination
    @method
    class iter_history(iter_history_generic):
        head_xpath = '//table[@id="creditHistory" or @id="TransactionHistory"]/thead/tr/th'
        item_xpath = '//table[@id="creditHistory" or @id="TransactionHistory"]/tbody/tr'


class LifeHistoryInvestmentsPage(TransactionsPage):
    @method
    class get_investment(TableElement):
        item_xpath = '//table[@id="assets"]/tbody/tr'
        head_xpath = '//table[@id="assets"]/thead/tr[1]/th'

        col_label = "Fonds"
        col_quantity = "Nombre de parts"
        col_unitvalue = "Valeur part"
        col_valuation = "Total"
        col_portfolio_share = "Répartition"

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(TableCell("label"))
            obj_quantity = MyDecimal(TableCell("quantity"))
            obj_unitvalue = MyDecimal(TableCell("unitvalue"))
            obj_valuation = MyDecimal(TableCell("valuation"))
            obj_portfolio_share = Eval(lambda x: x / 100, MyDecimal(TableCell("portfolio_share")))


class LoanHistoryPage(TransactionsPage):
    pass


class CardHistoryPage(TransactionsPage):

    def get_previous_date(self):
        return Attr('//a[@id="op_precedente"]', "date_recup", default=None)(self.doc)


class CardHistoryJsonPage(LoggedPage, JsonPage):

    def get_previous_date(self):
        return Dict("str_datePrecedente", default=None)(self.doc)

    def get_last_timestamp(self):
        # if we don't get the date_recup timestamp value in the html
        # we get the timestampOperation timestamp of the last transactions returned by the API
        all_tr = Dict("tab_historique", default=[])(self.doc)
        if all_tr:
            return all_tr[-1]["timestampOperation"]
        else:
            return None

    def on_load(self):
        # if I do a call to the API without the good dateRecup value that the API want
        # will return a dict of dict instead of a list of dict
        #
        # what we receive (and what we want) with the good dateRecup value:
        #   [{'date': '...', 'label': '...', 'amount': '...'}, {'date': '...', 'label': '...', 'amount': '...'}]
        #
        # what we receive with a bad dateRecup (what we don't want):
        #   {"1": {'date': '...', 'label': '...', 'amount': '...'}, "2": {'date': '...', 'label': '...', 'amount': '...'}}
        #
        # this function converts the response to the good format if needed
        if isinstance(self.doc["tab_historique"], dict):
            self.doc["tab_historique"] = sorted(
                self.doc["tab_historique"].values(), key=lambda x: x["timestampOperation"], reverse=True
            )

        elif self.doc["tab_historique"] is None:
            # No transaction available, set value to empty dict
            # instead of null since we need an iterable
            self.doc["tab_historique"] = {}

    @method
    class iter_history(DictElement):
        item_xpath = "tab_historique"

        class item(ItemElement):
            klass = Transaction

            def obj_date(self):
                return datetime.datetime.strptime(
                    CleanText(Dict("timestampOperation"))(self), "%Y-%m-%d-%H.%M.%S.%f"
                ).date()

            obj_rdate = Date(CleanText(Dict("date")), dayfirst=True)
            obj_raw = CleanText(Dict("label"))
            obj_amount = CleanDecimal.French(Dict("amount"))

            def obj_type(self):
                debittype = Dict("mode")
                if debittype(self) == "Différé":
                    return Transaction.TYPE_DEFERRED_CARD
                else:
                    return Transaction.TYPE_CARD
