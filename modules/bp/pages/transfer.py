# Copyright(C) 2010-2011 Nicolas Duhamel
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
from datetime import datetime
from urllib.parse import urljoin

from woob.browser.elements import DictElement, ItemElement, ListElement, SkipItem, method
from woob.browser.filters.html import Attr, Link
from woob.browser.filters.javascript import JSVar
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, CleanText, Currency, Date, Env, Format, Regexp
from woob.browser.pages import JsonPage, LoggedPage, PartialHTMLPage
from woob.capabilities.bank import (
    AccountNotFound,
    AddRecipientBankError,
    Emitter,
    Recipient,
    Transfer,
    TransferBankError,
)
from woob.capabilities.base import NotAvailable, empty, find_object
from woob.exceptions import BrowserUnavailable
from woob.tools.capabilities.bank.iban import is_iban_valid
from woob.tools.capabilities.bank.transactions import FrenchTransaction

from .base import MyHTMLPage


class CheckTransferError(MyHTMLPage):
    def on_load(self):
        super().on_load()
        error = CleanText(
            """
            //span[@class="app_erreur"]
            | //p[@class="warning"]
            | //p[contains(text(), "Votre virement n'a pas pu être enregistré")]
        """
        )(self.doc)
        if error and "Votre demande de virement a été enregistrée le" not in error:
            raise TransferBankError(message=error)


class TransferChooseAccounts(LoggedPage, MyHTMLPage):
    def is_inner(self, text):
        for option in self.doc.xpath('//select[@id="donneesSaisie.idxCompteEmetteur"]/option'):
            if text == CleanText(".")(option):
                return True
        return False

    @method
    class iter_recipients(ListElement):
        def condition(self):
            return any(
                self.env["account_id"] in Attr(".", "value")(option)
                for option in self.page.doc.xpath('//select[@id="donneesSaisie.idxCompteEmetteur"]/option')
            )

        item_xpath = '//select[@id="idxCompteReceveur"]/option'

        class Item(ItemElement):
            klass = Recipient

            def condition(self):
                return self.el.attrib["value"] != "-1"

            def validate(self, obj):
                # Some international external recipients show those infos:
                # INT - CA - 0815304220511006                   - CEGEP CANADA
                # Skipping those for the moment.
                return not obj.iban or is_iban_valid(obj.iban)

            obj_category = Env("category")
            obj_label = Env("label")
            obj_id = Env("id")
            obj_currency = "EUR"
            obj_iban = Env("iban")
            obj_bank_name = Env("bank_name")
            obj__value = Attr(".", "value")

            def obj_enabled_at(self):
                return datetime.now().replace(microsecond=0)

            def parse(self, el):
                if (
                    any(s in CleanText(".")(el) for s in ["Avoir disponible", "Solde"])
                    or self.page.is_inner(CleanText(".")(el))
                    or not is_iban_valid(
                        CleanText(Attr(".", "value"))(el)
                    )  # if the id is not an iban, it is an internal id (for internal accounts)
                ):
                    self.env["category"] = "Interne"
                else:
                    self.env["category"] = "Externe"

                _id = CleanText(Attr(".", "value"))(el)
                if _id == self.env["account_id"]:
                    raise SkipItem()
                self.env["id"] = _id

                if self.env["category"] == "Interne":
                    try:
                        account = find_object(self.page.browser.get_accounts_list(), id=_id, error=AccountNotFound)
                        self.env["label"] = account.label
                        self.env["iban"] = account.iban
                    except AccountNotFound:
                        # Some internal recipients cannot be parsed on the website and so, do not
                        # appear in the iter_accounts. We can still do transfer to those accounts
                        # because they have an internal id (internal id = id that is not an iban).
                        self.env["iban"] = NotAvailable
                        raw_label = CleanText(".")(el)
                        if "-" in raw_label:
                            label = raw_label.split("-")

                            if not any(string in label[-1] for string in ["Avoir disponible", "Solde"]):
                                holder = label[-1]
                            else:
                                holder = label[-2]

                            self.env["label"] = f"{label[0].strip()} {holder.strip()}"
                        else:
                            self.env["label"] = raw_label
                    self.env["bank_name"] = "La Banque Postale"

                else:
                    self.env["iban"] = _id
                    raw_label = CleanText(".")(el).strip()
                    # Normally, a beneficiary label looks like that:
                    # <option value="FR932004...3817">CCP - FR 93 2004...38 17        - MR JOHN DOE</option>
                    # but sometimes, the label is short, as it can be customized by customers:
                    # <option value="FR932004...3817">JOHNJOHN</option>
                    self.env["bank_name"] = NotAvailable

                    label_parts = raw_label.split(" - ", 2)
                    if len(label_parts) == 3 and label_parts[1].replace(" ", "") == _id:
                        if label_parts[0].strip() in ["CCP", "PEL", "LJ", "CEL", "LDDS"]:
                            self.env["bank_name"] = "La Banque Postale"
                        self.env["label"] = label_parts[2].strip()
                    else:
                        self.env["label"] = raw_label

                if self.env["id"] in self.parent.objects:
                    # user add two recipients with same iban...
                    raise SkipItem()

    def init_transfer(self, account_id, recipient_value, amount):
        matched_values = [
            Attr(".", "value")(option)
            for option in self.doc.xpath('//select[@id="donneesSaisie.idxCompteEmetteur"]/option')
            if account_id in Attr(".", "value")(option)
        ]
        assert len(matched_values) == 1
        form = self.get_form(xpath='//form[@class="choix-compte"]')
        form["donneesSaisie.idxCompteReceveur"] = recipient_value
        form["donneesSaisie.idxCompteEmetteur"] = matched_values[0]
        form["donneesSaisie.montant"] = amount
        form.submit()

    @method
    class iter_emitters(ListElement):
        item_xpath = '//select[@id="donneesSaisie.idxCompteEmetteur"]/option[@value!="-1"]'

        class item(ItemElement):
            klass = Emitter

            obj_id = CleanText("./@value")
            obj_currency = Currency(".")

            def obj_balance(self):
                # Split item data and get the balance part
                item_string = CleanText(".")(self)
                if "Solde" not in item_string:
                    return NotAvailable

                return CleanDecimal.French().filter(item_string.split("Solde")[-1])

            def obj_label(self):
                """
                Label info is found at the start and the middle of the item data:
                'CCP - 12XXXX99 - MR JEAN DUPONT - Solde : 9 270,89 €' becomes 'CCP - MR JEAN DUPONT'.
                Sometimes the owner name and account number is not present so the label looks like this:
                'CCP - Solde : 9 270,89 €'
                """
                item_parts = list(map(str.strip, CleanText(".")(self).split("-")))
                if len(item_parts) > 2:
                    return f"{item_parts[0]} - {item_parts[2]}"
                else:
                    return item_parts[0]


class CompleteTransfer(LoggedPage, CheckTransferError):
    def complete_transfer(self, transfer):
        form = self.get_form(xpath="//form[@method]")
        if "commentaire" in form and transfer.label:
            # for this bank the 'commentaire' is not a real label
            # but a reason of transfer
            form["commentaire"] = transfer.label
        form["dateVirement"] = transfer.exec_date.strftime("%d/%m/%Y")
        form.submit()

    def get_blocage_popin_url_suffix(self):
        """Get the popin (popup) url suffix if transfer is not allowed for EpargneLoi6902 reason

        One of the expected value could be: "popinVOEpargneVersInterBancaire"
        """
        suffix = JSVar(
            CleanText("//script[contains(text(), 'doAfficherPopinBlocage =')]"),
            var="doAfficherPopinBlocage",
            default=NotAvailable,
        )(self.doc)
        # When not needed, the var value is an empty string ''
        if empty(suffix) or not suffix:
            return None
        return suffix


class Loi6902TransferPage(LoggedPage, MyHTMLPage):
    ENCODING = "iso-8859-15"

    def detect_encoding(self):
        # Ignore the html level encoding detection because the document is lying
        # header reported encoding will be automatically used instead
        return None

    def get_popup_message(self):
        return Format(
            "%s %s",
            CleanText(
                '//div[@id="pop_up_virement_epargne_loi_6902_inter_haut" or @id="pop_up_virement_epargne_loi_6902_intra_haut"]//div[@class="textFCK"]'
            ),
            CleanText(
                '//div[@id="pop_up_virement_epargne_loi_6902_inter_milieu" or @id="pop_up_virement_epargne_loi_6902_intra_milieu"]//div[@class="textFCK"]'
            ),
        )(self.doc)


class TransferConfirm(LoggedPage, CheckTransferError):
    def is_here(self):
        return (
            not CleanText('//p[contains(text(), "Vous pouvez le consulter dans le menu")]')(self.doc)
            or self.doc.xpath(
                '//input[@title="Confirmer la demande de virement"]'
            )  # appears when there is no need for otp/polling
            or self.doc.xpath(
                "//span[contains(text(), 'cliquant sur le bouton \"CONFIRMER\"')]"
            )  # appears on the page when there is a 'Confirmer' button or not
            or CleanText('//label[contains(text(), "saisir votre code de validation reçu par SMS)]')(
                self.doc
            )  # appears when there is an otp
        )

    def is_certicode_needed(self):
        return CleanText('//div[contains(text(), "veuillez saisir votre code de validation reçu par SMS")]')(self.doc)

    def is_certicode_plus_needed(self):
        return CleanText('//script[contains(text(), "popupChoixDevice")]')(self.doc)

    def get_device_choice_url(self):
        device_choice_popup_js = CleanText('//script[contains(text(), "popupChoixDevice")]')(self.doc)
        if device_choice_popup_js:
            device_choice_url = re.search(r"(?<=urlPopin = )\"(.*popUpDeviceChoice\.jsp)\";", device_choice_popup_js)
            if device_choice_url:
                return device_choice_url.group(1)

    def get_sms_form(self):
        form = self.get_form(name="SaisieOTP")
        # Confirmation url is relative to the current page. We need to
        # build it now or the relative path will fail when reloading state
        # because we do not reload the url in it.
        form["url"] = self.absurl(form.url)
        return form

    def confirm(self):
        form = self.get_form(id="formID")
        form.submit()

    def handle_response(self, transfer):
        # handle error
        error_msg = CleanText('//div[@id="blocErreur"]')(self.doc)
        if error_msg:
            raise TransferBankError(message=error_msg)
        # handle 'Opération engageante - Code personnel périmé' error
        response_title = CleanText('//h1[@class="title-level1"]')(self.doc)
        if "Code personnel périmé" in response_title:
            raise TransferBankError(message=response_title)

        # There used to be a check for the debit account here; however,
        # the transfer confirmation and summary no longer contain the
        # identifier of the debit account, and the label is different,
        # so it is difficult to identify that the selected account is the
        # right one with certainty, so we choose not to check this for now.
        #
        # The recipient check appears to still work though, so we keep this
        # one.
        recipient_txt = CleanText('//form//h3[contains(text(), "créditer")]//following::span[1]', replace=[(" ", "")])(
            self.doc
        )

        assert transfer.recipient_id in recipient_txt, "Something went wrong"

        exec_date = Date(
            CleanText('//h3[contains(text(), "virement")]//following::span[@class="date"]'), dayfirst=True
        )(self.doc)

        amount_element = self.doc.xpath(
            '//h3[contains(text(), "Montant du virement")]//following::span[@class="price"]'
        )[0]
        r_amount = CleanDecimal.French(".")(amount_element)
        currency = FrenchTransaction.Currency(".")(amount_element)

        tr = Transfer()
        for key, value in transfer.iter_fields():
            setattr(tr, key, value)
        tr.currency = currency
        tr.amount = r_amount
        tr.exec_date = exec_date

        return tr


class TransferSummary(LoggedPage, CheckTransferError):
    is_here = '//h3[contains(text(), "Récapitulatif")]'

    def handle_response(self, transfer):
        summary_filter = CleanText('//div[contains(@class, "bloc-recapitulatif")]//p')

        # handle error
        if "Votre virement n'a pas pu" in summary_filter(self.doc):
            raise TransferBankError(message=summary_filter(self.doc))

        transfer_id = Regexp(summary_filter, r"référence n° (\d+)", default=None)(self.doc)
        # not always available
        if transfer_id and not transfer.id:
            transfer.id = transfer_id

        # WARNING: At this point, the transfer was made.
        # The following code is made to retrieve the transfer execution date,
        # so there is no falsy data.
        # But the bp website is unstable with changing layout and messages.
        # One of the goals here is for the code not to crash to avoid the user thinking
        # that the transfer was not made while it was.

        old_date = transfer.exec_date
        # the date was modified because on a weekend
        if "date correspondant à un week-end" in summary_filter(self.doc):
            transfer.exec_date = Date(
                Regexp(summary_filter, r"jour ouvré suivant \((\d{2}/\d{2}/\d{4})\)", default=""),
                dayfirst=True,
                default=NotAvailable,
            )(self.doc)

            self.logger.warning(
                "The transfer execution date changed from %s to %s",
                old_date.strftime("%Y-%m-%d"),
                transfer.exec_date.strftime("%Y-%m-%d"),
            )

        # made today
        elif "date du jour de ce virement" in summary_filter(self.doc):
            # there are several regexp for transfer date:
            # Date ([\d\/]+)|le ([\d\/]+)|suivant \(([\d\/]+)\)
            # be more passive to avoid impulsive reaction from user
            transfer.exec_date = Date(
                Regexp(summary_filter, r" (\d{2}/\d{2}/\d{4})", default=""), dayfirst=True, default=NotAvailable
            )(self.doc)

        # else: using the same date because the website does not give one

        if empty(transfer.exec_date):
            transfer.exec_date = old_date

        return transfer


class CreateRecipient(LoggedPage, MyHTMLPage):
    def on_load(self):
        super().on_load()
        if self.doc.xpath('//h1[contains(text(), "Service Désactivé")]'):
            raise BrowserUnavailable(CleanText('//p[img[@title="attention"]]/text()')(self.doc))

    def choose_country(self, recipient, is_bp_account):
        # if this is present, we can't add recipient currently
        more_security_needed = self.doc.xpath('//iframe[@title="Gestion de compte par Internet"]')
        if more_security_needed:
            raise AddRecipientBankError(
                message="Pour activer le service Certicode, nous vous invitons à vous rapprocher de votre Conseiller en Bureau de Poste."
            )

        form = self.get_form(name="SaisiePaysBeneficiaireVirement")
        form["compteLBP"] = str(is_bp_account).lower()
        form["beneficiaireBean.paysDestination"] = recipient.iban[:2]
        form.submit()


class ValidateCountry(LoggedPage, MyHTMLPage):
    def submit_recipient(self, recipient):
        form = self.get_form(name="CaracteristiquesBeneficiaireVirement")
        form["beneficiaireBean.nom"] = recipient.label
        form["beneficiaireBean.ibans[1].valeur"] = recipient.iban[2:4]
        form["beneficiaireBean.ibans[2].valeur"] = recipient.iban[4:8]
        form["beneficiaireBean.ibans[3].valeur"] = recipient.iban[8:12]
        form["beneficiaireBean.ibans[4].valeur"] = recipient.iban[12:16]
        form["beneficiaireBean.ibans[5].valeur"] = recipient.iban[16:20]
        form["beneficiaireBean.ibans[6].valeur"] = recipient.iban[20:24]
        form["beneficiaireBean.ibans[7].valeur"] = recipient.iban[24:]
        form["beneficiaireBean.intituleCompte"] = recipient.label
        form.submit()


class ValidateRecipient(LoggedPage, MyHTMLPage):
    def is_bp_account(self):
        msg = CleanText('//span[has-class("app_erreur")]')(self.doc)
        return (
            "Le n° de compte que vous avez saisi appartient à La Banque Postale, veuillez vérifier votre saisie." in msg
        )

    def get_confirm_link(self):
        return Link('//a[@title="confirmer la creation"]')(self.doc)


class CheckErrorsPage(LoggedPage, MyHTMLPage):
    def check_errors(self):
        error_msg = CleanText('//h2[contains(text(), "Compte rendu")]/following-sibling::p')(self.doc)
        if error_msg:
            raise AddRecipientBankError(message=error_msg)


class ConfirmPage(CheckErrorsPage):
    def get_device_choice_url(self):
        device_choice_popup_js = CleanText('//script[contains(text(), "popupChoixDevice")]')(self.doc)
        if device_choice_popup_js:
            device_choice_url = re.search(r"(?<=urlPopin = )\"(.*popUpDeviceChoice\.jsp)\";", device_choice_popup_js)
            if device_choice_url:
                return device_choice_url.group(1)

    def get_error_message(self):
        # Example message here:
        # "Votre code personnel Certicode Plus est arrivé à échéance. [...]"
        return CleanText('//div[@class="textFCK"]', default="")(self.doc)

    def set_browser_form(self):
        form = self.get_form(name="SaisieOTP")
        self.browser.sms_form = {k: v for k, v in form.items() if v}
        # Confirmation url is relative to the current page. We need to
        # build it now or the relative path will fail when reloading state
        # because we do not reload the url in it.
        self.browser.sms_form["url"] = urljoin(self.url, form.url)


class OtpErrorPage(LoggedPage, PartialHTMLPage):
    # Need PartialHTMLPage because sometimes we land on this page with
    # a status_code 302, so the page is empty and the build_doc crash.
    def get_error(self):
        return CleanText('//form//span[@class="warning" or @class="app_erreur"]')(self.doc)


class CerticodePlusSubmitDevicePage(LoggedPage, MyHTMLPage):
    def get_app_validation_message(self):
        # Mobile app message is too long, like this:
        # """ Une notification vous a été envoyée sur l’appareil que vous avez choisi: [PHONE].
        # Vous pouvez également retrouver l’opération en attente de validation en vous connectant
        # sur votre application mobile "La Banque Postale" avec vos identifiants et mot de passe
        # et en allant sur l’onglet "Gérer / Mes Opérations Certicode Plus". """
        # The first part is enough ...

        app_validation_message = CleanText('//main[@id="main"]//div[contains(text(), "Une notification vous a")]')(
            self.doc
        )
        assert app_validation_message, "The notification message is missing"

        msg_first_part = re.search(r"(.*)\. Vous pouvez", app_validation_message)
        if msg_first_part:
            app_validation_message = msg_first_part.group(1)

        return app_validation_message


class RcptSummary(CheckErrorsPage):
    pass


class ProTransferChooseAccounts(LoggedPage, JsonPage):
    @method
    class iter_emitters(DictElement):
        item_xpath = "groupesComptes/0/comptes"

        class item(ItemElement):
            klass = Emitter

            obj_id = Dict("numero")
            obj_balance = CleanDecimal.US(Dict("solde"))
            obj_label = Dict("intitule")
            obj_currency = "EUR"
