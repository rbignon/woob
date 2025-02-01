# -*- coding: utf-8 -*-

# Copyright(C) 2018 Célande Adrien
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
from datetime import date
from decimal import Decimal
from json import loads

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    CleanDecimal,
    CleanText,
    Coalesce,
    Currency,
    Env,
    Eval,
    Field,
    Format,
    FromTimestamp,
    QueryValue,
    Type,
)
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, pagination
from woob.capabilities import NotAvailable
from woob.capabilities.bank import Account, Loan
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.profile import Person
from woob.exceptions import AuthMethodNotImplemented, BrowserIncorrectPassword, BrowserUnavailable
from woob.tools.capabilities.bank.investments import is_isin_valid
from woob.tools.capabilities.bank.transactions import FrenchTransaction
from woob.tools.date import parse_french_date


class Transaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r"^.*Virement (?P<text>.*)"), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r"PRELEV SEPA (?P<text>.*)"), FrenchTransaction.TYPE_ORDER),
        (re.compile(r".*Prélèvement.*"), FrenchTransaction.TYPE_ORDER),
        (re.compile(r"^(REGL|Rgt)(?P<text>.*)"), FrenchTransaction.TYPE_ORDER),
        (
            re.compile(r"^(?P<text>.*) Carte \d+( CB\.XXXXX(\d){3})? LE (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{2})"),
            FrenchTransaction.TYPE_CARD,
        ),
        (
            re.compile(r"^(?P<text>.*) Carte \d+ CB\.\w+ LE (?P<dd>\d{2})\/(?P<mm>\d{2})\/(?P<yy>\d{2})"),
            FrenchTransaction.TYPE_CARD,
        ),
        (re.compile(r"^Débit mensuel.*"), FrenchTransaction.TYPE_CARD_SUMMARY),
        (
            re.compile(
                r"^Retrait d'espèces à un DAB (?P<text>.*) CARTE [X\d]+ LE (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{2})"
            ),
            FrenchTransaction.TYPE_WITHDRAWAL,
        ),
        (re.compile(r"^Paiement de chèque (?P<text>.*)"), FrenchTransaction.TYPE_CHECK),
        (re.compile(r"^(Cotisation|Intérêts) (?P<text>.*)"), FrenchTransaction.TYPE_BANK),
        (
            re.compile(
                r"(?P<text>Remise (de )?(C|c)hèque\(s\) \d{7})( (V|v)otre remise du : (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{4}))?"
            ),
            FrenchTransaction.TYPE_DEPOSIT,
        ),
        (re.compile(r"^Versement (?P<text>.*)"), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r"^Frais transaction carte (\d){7}"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^Frais tenue de compte"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^Commission virement instantané émis"), FrenchTransaction.TYPE_BANK),
        (
            re.compile(r"^(?P<text>.*)LE (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{2})\s*(?P<text2>.*)"),
            FrenchTransaction.TYPE_UNKNOWN,
        ),
    ]


class MyJsonPage(JsonPage):
    def get_content(self):
        return self.doc.get("content", {})


class HomePage(LoggedPage, HTMLPage):
    pass


class LoginPage(LoggedPage, HTMLPage):
    pass


class AccountsTwoFAPage(JsonPage):
    pass


class InitAuthentPage(JsonPage):
    def get_authent_id(self):
        return Dict("content")(self.doc)


class AuthentResultPage(JsonPage):
    @property
    def logged(self):
        return self.get_status() == "AUTHORISED"

    def get_status(self):
        return Dict("content/status", default=None)(self.doc)


class SendSmsPage(JsonPage):
    pass


class TrustedDevicesPage(JsonPage):
    def get_error(self):
        error = CleanText(Dict("erreur/libelle"))(self.doc)
        if error != "OK":
            return error


class CheckOtpPage(TrustedDevicesPage):
    @property
    def logged(self):
        return CleanText(Dict("erreur/libelle"))(self.doc) == "OK"


class UniversePage(LoggedPage, MyJsonPage):
    def get_universes(self):
        universe_data = self.get_content()
        universes = {}
        universes[universe_data["universKey"]] = universe_data["title"]
        for universe in universe_data.get("menus", {}):
            universes[universe["universKey"]] = universe["title"]

        return universes


class TokenPage(MyJsonPage):
    pass


class MoveUniversePage(LoggedPage, HTMLPage):
    pass


class SwitchPage(LoggedPage, JsonPage):
    pass


class LoansPage(LoggedPage, JsonPage):
    @method
    class iter_loans(DictElement):
        def find_elements(self):
            return self.el.get("content", [])

        class item(ItemElement):
            klass = Loan

            obj_id = Format(
                "%s.%s",
                CleanText(Dict("comptePrets")),
                CleanText(Dict("numeroDossier")),
            )
            obj_label = Format(
                "%s %s",
                CleanText(Dict("intitule")),
                CleanText(Dict("libellePrets")),
            )
            obj_balance = CleanDecimal(Dict("montantCapitalDu/valeur"), sign="-")
            obj_currency = Currency(Dict("montantCapitalDu/monnaie/code"))
            obj_next_payment_amount = CleanDecimal.SI(
                Dict(
                    "montantProchaineEcheance/valeur",
                    default=NotAvailable,
                ),
                default=NotAvailable,
            )
            obj_next_payment_date = FromTimestamp(
                Dict(
                    "dateProchaineEcheance",
                    default=NotAvailable,
                ),
                millis=True,
                default=NotAvailable,
            )
            obj_last_payment_amount = CleanDecimal.SI(
                Dict(
                    "montantEcheancePrecedent/valeur",
                    default=NotAvailable,
                ),
                default=NotAvailable,
            )
            obj_duration = Type(
                CleanText(Dict("dureePret", default=None), default=NotAvailable),
                type=int,
                default=NotAvailable,
            )
            obj_type = Account.TYPE_LOAN
            obj_rate = CleanDecimal.SI(Dict("tauxNominal"))
            obj_total_amount = CleanDecimal.SI(Dict("montantInitial/valeur"))
            obj_maturity_date = FromTimestamp(Dict("dateFinPret"), millis=True)
            obj_insurance_amount = CleanDecimal.SI(Dict("montantPartAssurance/valeur"))
            obj__univers = Env("current_univers")
            obj__number = Field("id")


class AccountsPage(LoggedPage, MyJsonPage):
    ACCOUNT_TYPES = {
        "000": Account.TYPE_CHECKING,  # Compte à vue
        "001": Account.TYPE_SAVINGS,  # Livret Ile de France
        "002": Account.TYPE_SAVINGS,  # Livret Seine-et-Marne & Aisne
        "003": Account.TYPE_SAVINGS,  # Livret Normandie
        "004": Account.TYPE_SAVINGS,  # Livret Guadeloupe
        "005": Account.TYPE_SAVINGS,  # Livret Martinique/Guyane
        "006": Account.TYPE_SAVINGS,  # Livret Réunion/Mayotte
        "011": Account.TYPE_CARD,  # Carte bancaire
        "013": Account.TYPE_LOAN,  # LCR (Lettre de Change Relevé)
        "020": Account.TYPE_SAVINGS,  # Compte sur livret
        "021": Account.TYPE_SAVINGS,
        "022": Account.TYPE_SAVINGS,  # Livret d'épargne populaire
        "023": Account.TYPE_SAVINGS,  # LDD Solidaire
        "025": Account.TYPE_SAVINGS,  # Livret Fidélis
        "027": Account.TYPE_SAVINGS,  # Livret A
        "037": Account.TYPE_SAVINGS,
        "070": Account.TYPE_SAVINGS,  # Compte Epargne Logement
        "077": Account.TYPE_SAVINGS,  # Livret Bambino
        "078": Account.TYPE_SAVINGS,  # Livret jeunes
        "080": Account.TYPE_SAVINGS,  # Plan épargne logement
        "081": Account.TYPE_SAVINGS,
        "086": Account.TYPE_SAVINGS,  # Compte épargne Moisson
        "097": Account.TYPE_CHECKING,  # Solde en devises
        "730": Account.TYPE_DEPOSIT,  # Compte à terme Optiplus
        "999": Account.TYPE_MARKET,  # no label, we use 'Portefeuille Titres' if needed
    }

    def iter_accounts(self, accnum, current_univers):
        seen = set()

        for content in self.get_content():
            if accnum != "00000000000" and content["numero"] != accnum:
                continue
            for poste in content["postes"]:
                a = Account()
                a._number = content["numeroLong"]
                a._nature = poste["codeNature"]
                a._codeSousPoste = poste["codeSousPoste"] if "codeSousPoste" in poste else None
                a._consultable = poste["consultable"]
                a._univers = current_univers
                a._parent_number = None
                a.id = "%s.%s" % (a._number, a._nature)

                if content["comptePEA"]:
                    a.type = Account.TYPE_PEA
                else:
                    a.type = self.ACCOUNT_TYPES.get(poste["codeNature"], Account.TYPE_UNKNOWN)
                if a.type == Account.TYPE_UNKNOWN:
                    self.logger.warning("unknown type %s" % poste["codeNature"])

                if a.type != Account.TYPE_CHECKING:
                    a._parent_number = a._number

                if "numeroDossier" in poste and poste["numeroDossier"]:
                    a._file_number = poste["numeroDossier"]
                    a.id += ".%s" % a._file_number

                if poste["postePortefeuille"]:
                    a.label = "{} Portefeuille Titres".format(content["intitule"].strip())
                    a.balance = Decimal(str(poste["montantTitres"]["valeur"]))
                    a.currency = poste["montantTitres"]["monnaie"]["code"].strip()
                    if not a.balance and not a.currency and "dateTitres" not in poste:
                        continue
                    yield a
                    continue

                if "libelle" not in poste:
                    continue

                a.label = " ".join([content["intitule"].strip(), poste["libelle"].strip()])
                if poste["numeroDossier"]:
                    a.label = "{} n°{}".format(a.label, poste["numeroDossier"])

                a.balance = Decimal(str(poste["solde"]["valeur"]))
                a.currency = poste["solde"]["monnaie"]["code"].strip()
                # Some accounts may have balance currency
                if "Solde en devises" in a.label and a.currency != "EUR":
                    a.id += str(poste["monnaie"]["codeSwift"])

                if a.id in seen:
                    # some accounts like "compte à terme fidélis" have the same _number and _nature
                    # but in fact are kind of closed, so worthless...
                    self.logger.warning(
                        "ignored account id %r (%r) because it is already used", a.id, poste.get("numeroDossier")
                    )
                    continue

                seen.add(a.id)
                yield a


class IbanPage(LoggedPage, MyJsonPage):
    def set_iban(self, account):
        iban_response = self.get_content()
        account.iban = CleanText(Dict("iban", default=None), default=NotAvailable)(iban_response)


class LinebourseLoginPage(LoggedPage, JsonPage):
    def get_linebourse_url(self):
        return Dict("content/url", default=None)(self.doc)

    def get_linebourse_token(self):
        return Dict("content/token", default=None)(self.doc)


class LifeInsurancesPage(LoggedPage, JsonPage):
    def check_error(self):
        error_code = Dict("erreur/code", default=None)(self.doc)
        if error_code and int(error_code) != 0:
            message = Dict("erreur/libelle", default=None)(self.doc)

            if error_code in ("90000", "1000"):
                raise BrowserUnavailable()

            raise AssertionError(f"Unhandled error {error_code}: {message}")

    @method
    class iter_lifeinsurances(DictElement):
        def condition(self):
            return "content" in self.el

        item_xpath = "content"

        class iter_accounts(DictElement):
            item_xpath = "avoirs/contrats"

            def get_owner(self):
                return CleanText(Dict("titulaire"))(self)

            class item(ItemElement):
                klass = Account

                obj_balance = CleanDecimal(Dict("valorisation"))
                obj_type = Account.TYPE_LIFE_INSURANCE
                obj_currency = "EUR"
                obj__univers = Env("univers")
                obj__number = Field("id")

                def obj_id(self):
                    return Eval(str, Dict("numero"))(self)

                def obj_label(self):
                    return "%s - %s" % (CleanText(Dict("libelleProduit"))(self), self.parent.get_owner())

                def obj__parent_number(self):
                    return CleanText(Dict("cptRattachement"))(self).rstrip("0")

                # Investments are already present in this JSON,
                # so we fill the lists of Investment objects now
                class obj__investments(DictElement):
                    item_xpath = "allocations"

                    class item(ItemElement):
                        klass = Investment

                        obj_label = CleanText(Dict("libelle"))
                        obj_valuation = CleanDecimal(Dict("montant"))

                        def obj_code_type(self):
                            if is_isin_valid(CleanText(Dict("code"))(self)):
                                return Investment.CODE_TYPE_ISIN
                            return NotAvailable

                        def obj_code(self):
                            code = CleanText(Dict("code"))(self)
                            if is_isin_valid(code):
                                return code
                            return NotAvailable


class SearchPage(LoggedPage, JsonPage):
    def check_error(self):
        if Dict("erreur/code")(self.doc) != "0":
            raise BrowserUnavailable("API sent back an error code")

    def get_max_transactions(self):
        return Dict("content/total")(self.doc)

    @pagination
    @method
    class iter_history(DictElement):
        item_xpath = "content/operations"

        def next_page(self):
            # All transaction pages show the total number of transactions.
            # To obtain the next page, we simply use the _make_api_call method.
            # This method makes a POST to the url of the transaction page and
            # we increment the offset by 50 each time until the total number
            # of transactions or a limit of 50 000 is reached.
            current_offset = self.page.response.request.body
            current_offset = int(loads(current_offset)["from"])
            current_offset += self.env["max_length"]
            if current_offset < self.env["max_transactions"] and current_offset < 50000:
                return self.page.browser._make_api_call(
                    account=self.env["account"],
                    start_date=self.env["start_date"],
                    end_date=self.env["end_date"],
                    offset=current_offset,
                    max_length=self.env["max_length"],
                )

        class item(ItemElement):
            klass = Transaction

            obj_raw = Transaction.Raw(Format("%s %s", CleanText(Dict("libelle")), CleanText(Dict("details"))))
            obj_label = CleanText(Dict("libelle"))
            obj_amount = CleanDecimal(Dict("montant"))
            obj_category = Dict("categorie", default=NotAvailable)

            def get_date(self, timestamp):
                if isinstance(timestamp, date):
                    return timestamp
                return date.fromtimestamp(timestamp / 1000)

            def obj_coming(self):
                _coming = Dict("intraday")(self)
                _coming |= Field("date")(self) > self.env["today"]
                return _coming

            def obj_id(self):
                # If op['id'] is an uuid, it will be a different one for every scrape
                re_uuid = re.compile(r"[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}")
                tr_id = Dict("id")(self)
                if Dict("intraday")(self) or re_uuid.match(tr_id):
                    return ""
                return tr_id

            def obj_date(self):
                if self.env["account_type"] == Account.TYPE_CARD:
                    tr_date = Coalesce(Dict("dateDebit", default=NotAvailable), Dict("dateOperation"))(self)
                else:
                    tr_date = Dict("dateOperation")(self)
                return self.get_date(tr_date)

            def obj_rdate(self):
                if self.env["account_type"] == Account.TYPE_CARD:
                    rdate = self.obj.rdate or Dict("dateOperation", default=NotAvailable)(self)
                elif self.env["account_type"] == Account.TYPE_CHECKING:
                    json_date = Coalesce(
                        Dict("dateValeur", default=NotAvailable),
                        Dict("dateOperation", default=NotAvailable),
                        default=NotAvailable,
                    )(self)
                    rdate = self.obj.rdate or json_date
                else:
                    rdate = Coalesce(
                        Dict("dateOperation", default=NotAvailable),
                        Dict("dateDebit", default=NotAvailable),
                        default=NotAvailable,
                    )(self)

                if rdate:
                    rdate = self.get_date(rdate)

                if self.env["account_type"] == Account.TYPE_CHECKING and rdate and rdate > Field("date")(self):
                    rdate = NotAvailable

                return rdate

            def obj_vdate(self):
                vdate = Coalesce(
                    Dict("dateValeur", default=NotAvailable),
                    Dict("dateDebit", default=NotAvailable),
                    Dict("dateOperation", default=NotAvailable),
                )(self)
                if vdate:
                    vdate = self.get_date(vdate)
                return vdate

            def obj_type(self):
                if self.obj.type == Transaction.TYPE_CARD and self.env["account_type"] == Account.TYPE_CARD:
                    return Transaction.TYPE_DEFERRED_CARD
                return self.obj.type

            def validate(self, obj):
                # If rdate and date of the transaction are too far apart we skip the transaction
                if not Field("rdate")(self):
                    return True
                return abs(Field("rdate")(self).year - Field("date")(self).year) < 2


class ProfilePage(LoggedPage, MyJsonPage):
    def get_profile(self):
        profile = Person()

        content = self.get_content()

        profile.name = content["prenom"] + " " + content["nom"]
        profile.address = content["adresse"] + " " + content["codePostal"] + " " + content["ville"]
        profile.country = content["pays"]
        profile.birth_date = parse_french_date(content["dateNaissance"]).date()

        return profile


class ErrorPage(LoggedPage, HTMLPage):
    def on_load(self):
        if "gestion-des-erreurs/erreur-pwd" in self.url:
            raise BrowserIncorrectPassword(CleanText("//h3")(self.doc))
        if "gestion-des-erreurs/opposition" in self.url:
            # need a case to retrieve the error message
            raise BrowserIncorrectPassword("Votre compte a été désactivé")
        if "/pages-gestion-des-erreurs/erreur-technique" in self.url:
            errmsg = CleanText("//h4")(self.doc)
            raise BrowserUnavailable(errmsg)
        if "/pages-gestion-des-erreurs/message-tiers-oppose" in self.url:
            # need a case to retrieve the error message
            raise AuthMethodNotImplemented(
                "Impossible de se connecter au compte car l'identification en 2 étapes a été activée"
            )


class ErrorCodePage(HTMLPage):
    def get_code(self):
        return QueryValue(None, "errorCode").filter(self.url)


class ErrorMsgPage(HTMLPage):
    def get_msg(self):
        return CleanText('//label[contains(@class, "error")]', default=None)(self.doc)


class UnavailablePage(HTMLPage):
    def is_here(self):
        return CleanText('//h1[contains(text(), "Site en maintenance")]', default=None)(self.doc)

    def on_load(self):
        msg = CleanText('//div[contains(text(), "intervention technique est en cours")]', default=None)(self.doc)
        if msg:
            raise BrowserUnavailable(msg)
        raise AssertionError("Ended up to this error page, message not handled yet.")
