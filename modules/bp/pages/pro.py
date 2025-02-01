# Copyright(C) 2014  Romain Bignon
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

from urllib.parse import parse_qsl, urlparse

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.html import Attr
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, CleanText, Date, Format, Map
from woob.browser.pages import JsonPage, LoggedPage
from woob.capabilities.bank import Account, AccountOwnerType
from woob.capabilities.base import NotAvailable
from woob.capabilities.profile import Company
from woob.exceptions import ActionNeeded, ActionType, BrowserIncorrectPassword

from .accounthistory import Transaction
from .base import MyHTMLPage


class RedirectPage(LoggedPage, MyHTMLPage):
    def check_for_perso(self):
        return self.doc.xpath(
            """//p[contains(text(), "L'identifiant utilisé est celui d'un compte de Particuliers")]"""
        )

    def get_error(self):
        return CleanText('//div[contains(@class, "bloc-erreur")]/h3')(self.doc)

    def is_logged(self):
        return "Vous êtes bien authentifié" in CleanText('//p[@class="txt"]')(self.doc)


ACCOUNT_TYPES = {
    "COMPTE_PLACEMENT": Account.TYPE_MARKET,  # seen for a compte titre
    "COMPTE_EPARGNE": Account.TYPE_SAVINGS,
    "COMPTE_COURANT": Account.TYPE_CHECKING,
}

TRANSACTION_TYPES = {
    # TODO: 12+ categories ? (bank type id is at least up to 12)
    "Prélèvement": Transaction.TYPE_ORDER,
    "Achat CB": Transaction.TYPE_CHECK,
    "Virement": Transaction.TYPE_TRANSFER,
    "Frais/Taxes/Agios": Transaction.TYPE_BANK,
    "Versement": Transaction.TYPE_CASH_DEPOSIT,
    "Chèque": Transaction.TYPE_CHECK,
    "Retrait": Transaction.TYPE_WITHDRAWAL,
    "Annul/Régul/Extourn": Transaction.TYPE_PAYBACK,
    "Remise chèques": Transaction.TYPE_DEPOSIT,
}


class ProAccountsList(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):
        def find_elements(self):
            """
            Structure of json:
                {
                    "comptesBancaires": {
                        "comptes": [{...}],
                        "...": ...,
                    },
                    "comptesEpargnesEtPlacements": {
                        "comptes": [{...}],
                        "...": ...,
                    },
                    "financements": {
                        "...": ...,
                    }
                    "groupesPersos": ...,
                    "indicateurCarte": ...,
                    "numeroCampagne": ...
                }
            """
            for data in self.el.values():
                if not isinstance(data, dict):
                    continue
                for account in data.get("comptes", []):
                    yield account

        class item(ItemElement):
            klass = Account

            obj_id = Dict("numero")
            obj_balance = CleanDecimal.US(Dict("solde"))
            obj_currency = "EUR"
            obj_type = Map(Dict("type"), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)
            obj_owner_type = AccountOwnerType.ORGANIZATION
            obj__account_holder = NotAvailable

            # The intituleCourt is usually the type of account, like CCP for a checking account
            # or LIV for a savings account.
            # The intituleDetenteur is the owner of the account.
            obj_label = CleanText(
                Format(
                    "%s %s",
                    Dict("intituleCourt"),
                    Dict("intituleDetenteur"),
                )
            )


class ProAccountHistory(LoggedPage, JsonPage):
    @method
    class iter_history(DictElement):
        class item(ItemElement):
            klass = Transaction

            obj_label = Dict("libelle")
            obj_date = Date(Dict("date"))  # skip time since it is always 00:00:00. Days last.

            # transaction typing: don't rely on labels as the bank already provides types.
            obj_type = Map(Dict("libelleNature"), TRANSACTION_TYPES, Transaction.TYPE_UNKNOWN)

            def obj_amount(self):
                amount = CleanDecimal.US(Dict("montant"))(self)  # absolute value
                sign = Dict("codeSens")(self)
                if sign == "D":  # debit
                    return -amount
                elif sign == "C":  # credit
                    return amount
                else:
                    raise AssertionError("unhandled value for transaction sign")


class DownloadRib(LoggedPage, MyHTMLPage):
    def get_rib_value(self, acc_id):
        opt = self.doc.xpath('//select[@id="idxSelection"]/optgroup//option')
        for o in opt:
            if acc_id in o.text:
                return o.xpath("./@value")[0]
        return None


class RibPage(LoggedPage, MyHTMLPage):
    def get_iban(self):
        if self.doc.xpath('//div[@class="blocbleu"][2]//table[@class="datalist"]'):
            return (
                CleanText()
                .filter(self.doc.xpath('//div[@class="blocbleu"][2]//table[@class="datalist"]')[0])
                .replace(" ", "")
                .strip()
            )
        return None

    @method
    class get_profile(ItemElement):
        klass = Company

        obj_name = CleanText('//table[@class="datalistecart"]//td[@class="nom"]')
        obj_address = CleanText('//table[@class="datalistecart"]//td[@class="adr"]')


class RedirectAfterVKPage(MyHTMLPage):
    def detect_encoding(self):
        # Ignore the html level encoding detection because the document is lying
        # header reported encoding will be automatically used instead
        return None

    def check_pro_website_or_raise(self):
        error_message = CleanText('//div[@id="erreur_identifiant_particulier"]//div[has-class("textFCK")]//p')(self.doc)
        if error_message:
            website_error = "L'identifiant utilisé est celui d'un compte de Particuliers"
            # Due to the encoding, website_error and error_message strings can be slightly
            # different, for example 'é' can become 'Ã©'. So we decode website_error with
            # the self.encoding encoding in the condition.
            if website_error.encode().decode(self.encoding) in error_message:
                raise BrowserIncorrectPassword(website_error)
            raise AssertionError("Unhandled error message: %s" % error_message)


class SwitchQ5CPage(MyHTMLPage):
    pass


class Detect2FAPage(MyHTMLPage):
    def raise_if_2fa_needed(self):
        url = Attr('//iframe[@id="iFrame1"]', "src", default="")(self.doc)
        if url:
            twofa_type = dict(parse_qsl(urlparse(url).query)).get("action", "")
            if twofa_type != "NULL":  # seen so far: CERTICODE (sms), NULL (no 2fa activated by the user)
                self.logger.info("A two factor auth is required on this connection")
                raise ActionNeeded(
                    locale="fr-FR",
                    message="Une authentification forte est requise sur votre espace client",
                    action_type=ActionType.PERFORM_MFA,
                )
