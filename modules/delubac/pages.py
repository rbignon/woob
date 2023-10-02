# Copyright(C) 2015 Romain Bignon
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

import re


from woob.browser.pages import HTMLPage, LoggedPage
from woob.browser.elements import ItemElement, method, ListElement, TableElement
from woob.browser.filters.standard import CleanDecimal, CleanText, Date, Regexp, QueryValue, Field
from woob.browser.filters.html import Attr, Link, TableCell
from woob.capabilities.base import NotAvailable
from woob.capabilities.bank import Account
from woob.tools.captcha.virtkeyboard import SplitKeyboard
from woob.tools.capabilities.bank.transactions import FrenchTransaction


class DelubacVirtKeyboard(SplitKeyboard):
    char_to_hash = {
        '0': ('a9a91717d92c524179f1afae2c10a723', 'f7d02e19f182be5e13ccded38dda2dae'),
        '1': ('447127b3f969167d23a3fa8d67d16b92', 'def7ebdc49310708a6fa7bd03e15befe'),
        '2': ('e8e7050f0fe079b7aca78645c28ee2e8', '8352b7c54bc2108212da5515052549d5'),
        '3': ('9ac3ef3e785d99a5b24ab9cfd3acfd18', '79a1389891b3711fcc4430d578efd7ab'),
        '4': ('1f1988abef340469414c5362e440c308', 'bed28cc3c1c93cb57f9ad05fd167644e'),
        '5': ('6a2f9bbaec0c9723bd8df2499c4a0f23', '549f3062dec406307ea1f7800fbad02c'),
        '6': ('3dfe2ffa48be5eed1b3bea330df31936', '613f0619a59d1903a278dde45820bfc3'),
        '7': ('6f82f2b9c6ce332b3c8d772c507bf6a3', '911e7fedf043af134a87d488b7be7def'),
        '8': ('615e63bb3c19c4aaa6e4b017c8e55786', '3d397219ce17fa420595eb8e3a838724'),
        '9': ('ce848fbd07daa83941ad886d34bf8b28', '42149d7cb18c0f43e80b87ca99b4a411'),
    }


class LoginPage(HTMLPage):
    def login(self, username, password):
        imgs = {}
        for img_elem in self.doc.xpath('//form[@name="entKbvLoginForm"]//img[@class="login-matrix-key"]'):
            img_src = self.browser.open(img_elem.attrib["src"], is_async=True).result().content
            img_code = re.search(r"[A-Z]{3}\|", img_elem.attrib['onclick']).group(0)
            imgs[img_code] = img_src

        form = self.get_form(name='entKbvLoginForm')
        form['josso_username'] = username
        form['josso_password'] = DelubacVirtKeyboard(imgs).get_string_code(password)

        form.submit()


class LoginResultPage(HTMLPage):
    def get_error(self):
        return CleanText('//div[contains(@class, "hidden-errors")]')(self.doc)

    def get_sca_message(self):
        return CleanText('.//form[@name="usernameLoginForm"]/div[1]')(self.doc)


class AccountsPage(LoggedPage, HTMLPage):
    def get_rib_link(self):
        return Regexp(
            Attr('.//a[contains(@onclick, "pdf-rib")]', 'onclick', default=''),
            r'javascript:webank\.openPopupUrl\(\'(.*?)\'\);',
            r'\1',
            default=None
        )(self.doc)

    @method
    class iter_accounts(ListElement):
        item_xpath = '//div[@id="compteCourantEUR"]//tr[@data-type="COMPTE"]'

        class item(ItemElement):
            klass = Account

            obj_id = Attr('.', "data-id")
            obj_number = Attr('.', "data-id")
            obj_label = CleanText('.//div[1]')
            obj_balance = CleanDecimal.US('.//div[@class="text-truncate text-end fs-sm fw-bold text-gray-600 text-hover-gray"]')
            obj_currency = 'EUR'
            obj_type = Account.TYPE_CHECKING

            obj_iban = QueryValue(
                Link('..//a[contains(@href, "check")]'),
                'rechercheComptes',
                default=NotAvailable
            )


class Transaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r'^VIR(EMENT)?( SEPA)? (?P<text>.*)'), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r'^PRLV (?P<text>.*)'), FrenchTransaction.TYPE_ORDER),
        (
            re.compile(r'^(?P<text>.*) CARTE \d+ PAIEMENT CB\s+(?P<dd>\d{2})(?P<mm>\d{2}) ?(.*)$'),
            FrenchTransaction.TYPE_CARD,
        ),
        (
            re.compile(r'^RETRAIT DAB (?P<dd>\d{2})(?P<mm>\d{2}) (?P<text>.*) CARTE [\*\d]+'),
            FrenchTransaction.TYPE_WITHDRAWAL,
        ),
        (re.compile(r'^CHEQUE( (?P<text>.*))?$'), FrenchTransaction.TYPE_CHECK),
        (re.compile(r'^(F )?COTIS\.? (?P<text>.*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(REMISE|REM.CHQ) (?P<text>.*)'), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r'^(?P<text>.*)(?P<dd>\d{2})(?P<mm>\d{2}) CARTE BLEUE'), FrenchTransaction.TYPE_CARD),
        (re.compile(r'^PRVL SEPA (?P<text>.*)'), FrenchTransaction.TYPE_ORDER),
        (re.compile(r'^(?P<text>(INT. DEBITEURS).*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(?P<text>.*(VIR EMIS).*)'), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r'^(?P<text>.*(\bMOUVEMENT\b).*)'), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r'^(?P<text>.*(ARRETE TRIM.).*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(?P<text>.*(TENUE DE DOSSIE).*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(?P<text>.*(RELEVE LCR ECH).*)'), FrenchTransaction.TYPE_ORDER),
        (re.compile(r'^(?P<text>.*(\+ FORT DECOUVERT).*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(?P<text>.*(EXTRANET @THEMI).*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(?P<text>.*(REL CPT DEBITEU).*)'), FrenchTransaction.TYPE_ORDER),
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
        (re.compile(r'^CARTE DU'), FrenchTransaction.TYPE_CARD),
        (re.compile(r'^(VIR (SEPA)?|Vir|VIR.)(?P<text>.*)'), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r'^VIREMENT DE (?P<text>.*)'), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r'^(CHQ|CHEQUE) (?P<text>.*)'), FrenchTransaction.TYPE_CHECK),
        (re.compile(r'^(PRLV SEPA|PRELEVEMENT) (?P<text>.*)'), FrenchTransaction.TYPE_ORDER),
    ]


class HistoryPage(LoggedPage, HTMLPage):
    def search_transactions_form(self, account):
        form = self.get_form(id='searchOperations')
        form['actionMethod'] = 'search'
        form['compte'] = account.id
        form.submit()

    def has_no_transaction(self):
        return CleanText('//table/tbody/tr[contains(@class, "tile")]/td[1]')(self.doc) == 'Aucune donnée'

    @method
    class iter_history(TableElement):
        head_xpath = '//table[@id="table-search-result"]/thead/tr/th'
        item_xpath = '//table[@id="table-search-result"]/tbody/tr[contains(@class, "tile")]'

        col_date = ["Date d'opération", 'Transaction date']
        col_vdate = ['Date de valeur', 'Value date']
        col_raw = ["Libellé de l'opération", 'Transaction label']
        col_amount = ['Montant', 'Amount']

        class item(ItemElement):
            klass = Transaction

            obj_date = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_vdate = Date(CleanText(TableCell('vdate')), dayfirst=True)
            obj_raw = obj_label = Transaction.Raw(TableCell('raw'))
            obj_amount = CleanDecimal.US(CleanText(TableCell('amount')))

            def condition(self):
                return Field('amount')(self)
