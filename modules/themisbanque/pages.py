# -*- coding: utf-8 -*-

# Copyright(C) 2015      Romain Bignon
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

from woob.browser.elements import ItemElement, TableElement, method
from woob.browser.filters.html import ColumnNotFound, Link, TableCell
from woob.browser.filters.standard import Async, CleanDecimal, CleanText, Field, Join, Regexp
from woob.browser.pages import HTMLPage, LoggedPage, PDFPage, pagination
from woob.capabilities.bank import Account
from woob.capabilities.base import NotAvailable
from woob.capabilities.profile import Profile
from woob.exceptions import BrowserIncorrectPassword
from woob.tools.capabilities.bank.iban import is_iban_valid
from woob.tools.capabilities.bank.transactions import FrenchTransaction
from woob.tools.pdf import extract_text


class MyCleanText(CleanText):
    @classmethod
    def clean(cls, txt, children=True, newlines=True, transliterate=False, normalize="NFC", **kwargs):
        if not isinstance(txt, str):
            txt = "\n".join([t.strip() for t in txt.itertext()])

        return txt


class LoginPage(HTMLPage):
    def login(self, username, password):
        form = self.get_form()
        form["identifiant"] = username
        form["motpasse"] = password
        form.submit()


class LoginConfirmPage(HTMLPage):
    def on_load(self):
        label = CleanText('//td[has-class("ColonneLibelle")]')(self.doc)
        if label == "Authentification incorrecte":
            raise BrowserIncorrectPassword(label)


class AccountsPage(LoggedPage, HTMLPage):
    def get_acc_link(self):
        msg = CleanText('//body[@class="message"]')(self.doc)
        if msg:
            acc_link = Link('//div[@class="Boutons"]/a', "href")(self.doc)
            return acc_link

    @method
    class iter_accounts(TableElement):
        item_xpath = '//table[has-class("TableBicolore")]//tr[@id and count(td) > 4]'
        head_xpath = '//table[has-class("TableBicolore")]//tr/td[@id]/@id'

        col_id = "idCompteLibelle"
        col_label = "idCompteIntitule"
        col_balance = "idCompteSolde"
        col_currency = "idCompteSoldeUM"
        col_rib = "idCompteRIB"
        col_type = "idCompteNature"

        class item(ItemElement):
            klass = Account

            def condition(self):
                return (
                    CleanDecimal(TableCell("balance"), replace_dots=True, default=NotAvailable)(self)
                    is not NotAvailable
                )

            TYPE = {
                "COMPTE COURANT": Account.TYPE_CHECKING,
                "COMPTE TRANSACTION": Account.TYPE_CHECKING,
                "COMPTE ORDINAIRE": Account.TYPE_CHECKING,
            }
            TYPE_BY_LABELS = {
                "CAV": Account.TYPE_CHECKING,
            }

            obj_id = CleanText(TableCell("id"))
            obj_label = CleanText(TableCell("label"))
            obj_currency = FrenchTransaction.Currency(TableCell("currency"))
            obj_balance = CleanDecimal(TableCell("balance"), replace_dots=True)

            def obj__link(self):
                return Link(TableCell("id")(self)[0].xpath("./a"), default=None)(self)

            def obj__url(self):
                return Link(TableCell("rib")(self)[0].xpath('./a[img[starts-with(@alt, "RIB")]]'), default=None)(self)

            def load_iban(self):
                link = Link(TableCell("rib")(self)[0].xpath('./a[img[starts-with(@alt, "RIB")]]'), default=None)(self)
                return self.page.browser.async_open(link)

            def obj_type(self):
                try:
                    el_to_check = CleanText(TableCell("type"))(self)
                    type_dict = self.TYPE
                except ColumnNotFound:
                    el_to_check = Field("label")(self)
                    type_dict = self.TYPE_BY_LABELS

                for k, v in type_dict.items():
                    if el_to_check.startswith(k):
                        return v
                return Account.TYPE_UNKNOWN

            def obj_iban(self):
                rib_page = Async("iban").loaded_page(self)
                if "RibPdf" in rib_page.url:
                    return rib_page.get_iban()
                return (
                    Join(
                        "",
                        Regexp(
                            CleanText('//td[has-class("ColonneCode")][contains(text(), "IBAN")]'),
                            r"\b((?!IBAN)[A-Z0-9]+)\b",
                            nth="*",
                        ),
                    )(rib_page.doc)
                    or NotAvailable
                )


class RibPage(LoggedPage, HTMLPage):
    def get_profile(self):
        profile = Profile()

        # profile is inside a <td> separated with a simple <br> without <span> or <div>
        profile_txt = MyCleanText('//div[@class="TableauAffichage"]/table/tr[3]/td[1]')(self.doc).split("\n")
        i_name = 0
        profile.name = ""
        # name can be on one, two, (more ?) lines, so we stop when line start by a number, we suppose it's the address number
        while not re.search(r"^\d", profile_txt[i_name]):
            profile.name += " " + profile_txt[i_name]
            i_name += 1

        profile.name = profile.name.strip()
        profile.address = ""
        # address is not always on two lines, so we consider every lines from here to before last are address, (last one is country)
        for i in range(i_name, len(profile_txt) - 1):
            profile.address += " " + profile_txt[i]

        profile.address = profile.address.strip()
        profile.country = profile_txt[-1]

        profile.name = profile.name.replace("MONSIEUR ", "").replace("MADAME ", "")

        return profile


class RibPDFPage(LoggedPage, PDFPage):
    def get_iban(self):
        text = extract_text(self.content)
        iban = re.search(r"IBAN([A-Z]{2}\d+)", text).group(1)
        assert is_iban_valid(iban), "did not parse IBAN properly"
        return iban


class Transaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r"^VIR(EMENT)?( SEPA)? (?P<text>.*)"), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r"^PRLV (?P<text>.*)"), FrenchTransaction.TYPE_ORDER),
        (
            re.compile(r"^(?P<text>.*) CARTE \d+ PAIEMENT CB\s+(?P<dd>\d{2})(?P<mm>\d{2}) ?(.*)$"),
            FrenchTransaction.TYPE_CARD,
        ),
        (
            re.compile(r"^RETRAIT DAB (?P<dd>\d{2})(?P<mm>\d{2}) (?P<text>.*) CARTE [\*\d]+"),
            FrenchTransaction.TYPE_WITHDRAWAL,
        ),
        (re.compile(r"^CHEQUE( (?P<text>.*))?$"), FrenchTransaction.TYPE_CHECK),
        (re.compile(r"^(F )?COTIS\.? (?P<text>.*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(REMISE|REM.CHQ) (?P<text>.*)"), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r"^(?P<text>.*)(?P<dd>\d{2})(?P<mm>\d{2}) CARTE BLEUE"), FrenchTransaction.TYPE_CARD),
        (re.compile(r"^PRVL SEPA (?P<text>.*)"), FrenchTransaction.TYPE_ORDER),
        (re.compile(r"^(?P<text>(INT. DEBITEURS).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(VIR EMIS).*)"), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r"^(?P<text>.*(\bMOUVEMENT\b).*)"), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r"^(?P<text>.*(ARRETE TRIM.).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(TENUE DE DOSSIE).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(RELEVE LCR ECH).*)"), FrenchTransaction.TYPE_ORDER),
        (re.compile(r"^(?P<text>.*(\+ FORT DECOUVERT).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(EXTRANET @THEMI).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(REL CPT DEBITEU).*)"), FrenchTransaction.TYPE_ORDER),
        (re.compile(r"^(?P<text>.*(\bAFFRANCHISSEMENT\b).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(REMISE VIREMENTS MAGNE).*)"), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r"^(?P<text>.*(\bEFFET\b).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(\bMANIP\.\b).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(INTERETS SUR REMISE PTF).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(REMISE ESCOMPTE PTF).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(RETENUE DE GARANTIE).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(RESTITUTION RETENUE GARANTIE).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(\bAMENDES\b).*)"), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r"^(?P<text>.*(\bOA\b).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^.* COTIS ANN (?P<text>.*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(FORFAIT CENT\.RE).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(ENVOI CB).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(RET\.SDD).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(RETOUR PVL ACD EXPERTISE).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(Annulation PAR REJ\/CHQ).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(REJET CHEQUE).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(CHQ PAYE INFRAC).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>^(CHQ IRREGULIER).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(ERREUR REMISE C).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>^(\bREMCHQ\b).*)"), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r"^(?P<text>^(RETOUR PVL).*)"), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r"^(?P<text>.*(\bTRANSFERT\b).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(\bCONFIRMATION\b).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(CAUTION AVEC GAGE).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(\bRAPATRIEMENT\b).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>.*(CHANGE REF).*)"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^CARTE DU"), FrenchTransaction.TYPE_CARD),
        (re.compile(r"^(VIR (SEPA)?|Vir|VIR.)(?P<text>.*)"), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r"^VIREMENT DE (?P<text>.*)"), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r"^(CHQ|CHEQUE) (?P<text>.*)"), FrenchTransaction.TYPE_CHECK),
        (re.compile(r"^(PRLV SEPA|PRELEVEMENT) (?P<text>.*)"), FrenchTransaction.TYPE_ORDER),
    ]


class HistoryPage(LoggedPage, HTMLPage):
    @pagination
    @method
    class get_operations(Transaction.TransactionsElement):
        def next_page(self):
            for script in self.page.doc.xpath("//script"):
                m = re.search(r"getCodePagination\('(\d+)','(\d+)','([^']+)'.*", script.text or "", re.MULTILINE)
                if m:
                    cur_page = int(m.group(1))
                    nb_pages = int(m.group(2))
                    baseurl = m.group(3)

                    if cur_page < nb_pages:
                        next_link = f"{baseurl}&numeroPage={cur_page + 1}&nbrPage={nb_pages}"
                        next_transactions_page = self.page.browser.location(next_link)

                        # Sometimes the website returns the same list of transactions for each history page.
                        # So we stop the iteration if the current transaction list and the transaction list
                        # of the next page are exactly the same.
                        transactions_table_xpath = '//div[has-class("TableauBicolore")]/table'
                        current_transactions = CleanText(transactions_table_xpath)(self)
                        next_transactions = CleanText(transactions_table_xpath)(
                            self.page.build_doc(next_transactions_page.content)
                        )

                        if current_transactions != next_transactions:
                            return self.page.browser.page
                        self.logger.warning(
                            "We stop the iteration because the bank seems to return us the same page in a loop"
                        )

        head_xpath = '//div[has-class("TableauBicolore")]/table/tr[not(@id)]/td'
        item_xpath = '//div[has-class("TableauBicolore")]/table/tr[@id and count(td) > 3]'

        col_date = ["Date comptable", "Date d'opération"]
        col_vdate = ["Date de valeur"]
        col_raw = ["Libellé de l'opération"]

        class item(Transaction.TransactionElement):
            pass
