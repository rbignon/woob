# Copyright(C) 2018      Sylvie Ye
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
import string
from datetime import date
from io import BytesIO
from itertools import chain

from PIL import Image, ImageFilter

from woob.browser.elements import ItemElement, ListElement, TableElement, method
from woob.browser.filters.html import Attr, TableCell
from woob.browser.filters.standard import CleanDecimal, CleanText, Currency, Date, Field, Format, Map, Regexp
from woob.browser.pages import HTMLPage, LoggedPage
from woob.capabilities.bank import (
    AddRecipientBankError,
    Emitter,
    Recipient,
    RecipientNotFound,
    Transfer,
    TransferBankError,
    TransferDateType,
    TransferFrequency,
)
from woob.capabilities.base import NotAvailable, find_object
from woob.tools.captcha.virtkeyboard import SimpleVirtualKeyboard


def remove_useless_form_params(form):
    # remove idJsp parameter in form
    for el in list(form):
        if "idJsp" in el:
            form.pop(el)
    return form


class TransferVirtualKeyboard(SimpleVirtualKeyboard):
    margin = 1
    tile_margin = 10

    symbols = {
        "0": "715df9c139fc7b46829526229c415a67",
        "1": "12d398f7f389711c5f8298ee68a8af28",
        "2": "f43ca3a5dd649d30bf02060ab65c4eff",
        "3": "b6dd7864cfd941badb0784be37f7eeb3",
        "4": (
            "7138d0a663eef56c699d85dc6c3ac639",
            "0faced58777f371097a7a70bb9570dd7",
        ),
        "5": "b71bd38e71ce0b611642a01b6900218f",
        "6": "f71f7249413c189165da7b588c2f0493",
        "7": "81fc65230d7df341e80d02e414f183d4",
        "8": "8106671a6b24aee3475d6f12a650f59b",
        "9": "e8c4567eb46dba5e2a92619076441a8a",
    }

    # Clean image
    def alter_image(self):
        # See ImageFilter.UnsharpMask from Pillow
        self.image = self.image.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
        # Convert to binary image
        self.image = Image.eval(self.image, lambda px: 0 if px <= 100 else 255)


class RecipientsPage(LoggedPage, HTMLPage):
    def get_extenal_recipient_ibans(self):
        ibans_xpath = (
            '//table[@id="saisieBeneficiaireSepa:idBeneficiaireSepaListe:'
            'table-beneficiaires"]//td[@class="destIban"]'
        )

        for iban in self.doc.xpath(ibans_xpath):
            yield CleanText(".", replace=[(" ", "")])(iban)

    @method
    class iter_recipients(TableElement):
        item_xpath = '//table[@id="saisieBeneficiaireSepa:idBeneficiaireSepaListe:' 'table-beneficiaires"]//tbody/tr'
        head_xpath = '//table[@id="saisieBeneficiaireSepa:idBeneficiaireSepaListe:' 'table-beneficiaires"]//th'

        col_id = "IBAN"
        col__rcpt_name = "Nom du bénéficiaire"
        col__acc_name = "Nom du compte"

        class item(ItemElement):
            klass = Recipient

            obj_id = CleanText(TableCell("id"), replace=[(" ", "")])
            obj_iban = Field("id")
            obj_label = Format("%s - %s", CleanText(TableCell("_acc_name")), CleanText(TableCell("_rcpt_name")))
            obj_category = "Externe"
            obj_enabled_at = date.today()
            obj_currency = "EUR"
            obj_bank_name = NotAvailable

    def go_add_new_recipient_page(self):
        add_new_recipient_btn_id = CleanText('//input[@class="btn_creer"]/@id')(self.doc)

        form = self.get_form(id="saisieBeneficiaireSepa")
        form = remove_useless_form_params(form)
        form[add_new_recipient_btn_id] = ""
        form.submit()

    def get_rcpt_after_sms(self, recipient):
        return find_object(self.iter_recipients(), iban=recipient.iban, error=RecipientNotFound)


class RecipientConfirmationPage(LoggedPage, HTMLPage):
    def on_load(self):
        errors_msg = (
            CleanText('//div[@class="anomalies"]//p[img]')(self.doc),
            CleanText('//div[@class="error" and contains(@style, "block")]')(self.doc),
        )

        if self.doc.xpath('//input[@class="erreur_champs"]'):
            raise AddRecipientBankError(message="Le code entré est incorrect.")

        for error_msg in errors_msg:
            if error_msg:
                raise AddRecipientBankError(message=error_msg)

        # To display some errors, the website use javascript to modify the style of error blocks.
        # So we need to check the javascript for modification on the error div style.
        text_js = CleanText('//script[contains(text(), "codeErrorFormat")]')(self.doc)
        if re.search(r'codeErrorFormat["\']\)\.style\.display = ["\']block["\']', text_js):
            error_msg = CleanText('//div[@id="codeErrorFormat"]')(self.doc)
            raise AddRecipientBankError(message=error_msg)

    def continue_new_recipient(self):
        continue_new_recipient_btn_id = CleanText('//input[@class="btn_continuer"]/@id')(self.doc)

        form = self.get_form(id="saisieBeneficiaireSepa")
        form = remove_useless_form_params(form)
        form[continue_new_recipient_btn_id] = ""
        form.submit()

    def send_code(self, code):
        confirm_btn_id = CleanText('//div[@id="idBoutonValiderSaisie"]/a[contains(@class, "btn_valider")]/@id')(
            self.doc
        )

        form = self.get_form(id="saisieBeneficiaireSepa")
        form = remove_useless_form_params(form)

        form[":cq_csrf_token"] = "undefined"
        form["saisieBeneficiaireSepa:_idcl"] = confirm_btn_id
        form["saisieBeneficiaireSepa:idBeneficiaireSepaGestion:codeBeneficiaire"] = code
        form.submit()

    def is_add_recipient_confirmation(self):
        return self.doc.xpath(
            '//table[@id="idConfirmation"]//p[contains(., "Votre bénéficiaire est en cours de création automatique")]'
        )

    def check_errors(self):
        # check if user can add new recipient
        errors_id = ("popinClientNonEligible", "popinClientNonEligibleBis")

        for error_id in errors_id:
            if self.doc.xpath("//script[contains(text(), \"showDivJQInfo('%s')\")]" % error_id):
                msg = CleanText('//div[@id="%s"]//p' % error_id)(self.doc)
                # get the first sentence of information message
                # beacause the message is too long and contains unnecessary recommendations
                raise AddRecipientBankError(message=msg.split(".")[0])


class AddRecipientPage(LoggedPage, HTMLPage):
    is_here = '//table[@id="tab_SaisieBenef"]'

    def set_new_recipient_iban(self, rcpt_iban):
        bank_field_disabled_id = CleanText('//input[@class="banqueFieldDisabled"]/@id')(self.doc)

        form = self.get_form(id="saisieBeneficiaireSepa")
        form = remove_useless_form_params(form)

        form[bank_field_disabled_id] = ""
        form["ibanContenuZone2"] = form["ibanContenuZone2Hidden"] = rcpt_iban[2:4]

        # fill iban part
        _iban_rcpt_part = 4
        for i in range(3, 10):
            form_key = f"ibanContenuZone{i}Hidden"
            form[form_key] = rcpt_iban[_iban_rcpt_part : _iban_rcpt_part + 4]
            if form[form_key]:
                form[f"ibanContenuZone{i}"] = form[form_key]
            _iban_rcpt_part += 4

        remove_form_keys = (
            "ibanContenuZone1",
            "bicContenuZone",
            "saisieBeneficiaireSepa:idBeneficiaireSepaGestion:boutonValiderInactifIban",
            "nomTitulaire",
            "intituleCompte",
        )
        for form_key in remove_form_keys:
            if form_key in form:
                form.pop(form_key)

        form["saisieBeneficiaireSepa:idBeneficiaireSepaGestion:paysIbanSelectionne"] = rcpt_iban[0:2]
        form.submit()

    def set_new_recipient_label(self, rcpt_label):
        self.browser.reload_state = True
        bank_field_disabled_id = self.doc.xpath('//input[@class="banqueFieldDisabled"]')
        continue_btn_id = CleanText('//input[@class="btn_continuer_sepa"]/@id')(self.doc)

        form = self.get_form(id="saisieBeneficiaireSepa")
        form = remove_useless_form_params(form)

        form[CleanText("./@id")(bank_field_disabled_id[0])] = CleanText("./@value")(bank_field_disabled_id[0])
        form[continue_btn_id] = ""
        form["intituleCompte"] = rcpt_label
        form["nomTitulaire"] = rcpt_label

        remove_form_keys = (
            "bicContenuZone",
            "ibanContenuZone1",
            "ibanContenuZone2",
            "ibanContenuZone3",
            "ibanContenuZone4",
            "ibanContenuZone5",
            "ibanContenuZone6",
            "ibanContenuZone7",
            "ibanContenuZone8",
            "ibanContenuZone9",
            "saisieBeneficiaireSepa:idBeneficiaireSepaGestion:boutonValiderActifIban",
            "saisieBeneficiaireSepa:idBeneficiaireSepaGestion:boutonValiderInactifIban",
            "saisieBeneficiaireSepa:idBeneficiaireSepaGestion:paysIbanSelectionne",
        )

        for form_key in remove_form_keys:
            if form_key in form:
                form.pop(form_key)

        # this send sms to user
        form.submit()


class RegisterTransferPage(LoggedPage, HTMLPage):
    def on_load(self):
        super().on_load()

        error_xpath = '//span[@class="erreur_phrase"]'
        if self.doc.xpath(error_xpath):
            error_msg = CleanText(error_xpath)(self.doc)
            raise TransferBankError(message=error_msg)

    def is_transfer_account(self, acc_id):
        valide_accounts_xpath = '//select[@id="compteEmetteurSelectionne"]//option[not(contains(@value,"vide0"))]'

        for valide_account in self.doc.xpath(valide_accounts_xpath):
            if acc_id == CleanText("./@value")(valide_account):
                return True
        return False

    # To get page with all recipients for an account
    def set_account(self, acc_id):
        form = self.get_form(id="idFormSaisieVirement")
        form["compteEmetteurSelectionne"] = acc_id
        form[":cq_csrf_token:"] = "undefined"

        remove_useless_form_params(form)
        form.pop("effetVirementDiffere")
        form.pop("effetVirementPermanent")
        form.pop("periodicite")
        form.pop("fin")
        form.pop("idFormSaisieVirement:idBtnAnnuler")
        form.pop("idFormSaisieVirement:idBtnValider")

        form.submit()

    # Get all recipient for an account
    def get_recipients(self):
        recipients_xpath = '//select[@id="compteDestinataireSelectionne"]/option[not(contains(@selected, "selected"))]'

        for recipient in self.doc.xpath(recipients_xpath):
            rcpt = Recipient()

            rcpt.label = re.sub(r" - \w{2,}\d{6,}", "", CleanText(".")(recipient))
            rcpt.iban = CleanText("./@value")(recipient)
            rcpt.id = rcpt.iban
            rcpt.enabled_at = date.today()
            rcpt.category = "Interne"

            yield rcpt

    # To do a transfer
    def fill_transfer_form(self, acc_id, recipient_iban, amount, reason, exec_date=None):
        form = self.get_form(id="idFormSaisieVirement")
        form["compteEmetteurSelectionne"] = acc_id
        form["compteDestinataireSelectionne"] = recipient_iban
        form["idFormSaisieVirement:montantVirement"] = str(amount).replace(".", ",")
        form["idFormSaisieVirement:libelleVirement"] = reason
        form["idFormSaisieVirement:idBtnValider"] = " "

        form.pop("idFormSaisieVirement:idBtnAnnuler")
        form.pop("effetVirementPermanent")
        form.pop("periodicite")
        form.pop("fin")

        # Deferred transfer
        if exec_date:
            form["effetVirementDiffere"] = exec_date.strftime("%d/%m/%Y")
            form["typeVirement"] = 2

            form.submit()
            return

        form.pop("effetVirementDiffere")

        form.submit()

    @method
    class iter_emitters(ListElement):
        item_xpath = '//select[@id="compteEmetteurSelectionne"]//option[not(contains(@value,"vide0"))]'

        class item(ItemElement):
            klass = Emitter

            obj_id = CleanText("./@value")
            obj_currency = Currency(CleanText('//td[@class="vrtMontant"]'))

            def obj_label(self):
                """
                Label looks like: 'Compte Ogoon - 12XXX27 - M. OU MME JEAN CHARLES DUPONT'
                We change it to: 'Compte Ogoon - M. OU MME JEAN CHARLES DUPONT'
                If the label is not the one we expect, just return it as is.
                """
                raw_label = CleanText(".")(self)
                if raw_label.count("-") != 2:
                    return raw_label
                label = raw_label.split("-")
                return f"{label[0].strip()} - {label[2].strip()}"

    @method
    class iter_transfers(TableElement):
        head_xpath = '//table[@id="idFormSaisieVirement:table-vrtDerniers"]//thead//th'
        item_xpath = '//table[@id="idFormSaisieVirement:table-vrtDerniers"]//tbody//tr'

        col_amount = "Montant"
        col_exec_date = "Date d'effet"
        col__rcpt_name = "Bénéficiaire"
        col__created_date = "Date de saisie"

        class item(ItemElement):
            klass = Transfer

            def condition(self):
                # website don't let you plan deferred for the same day
                # so if "date de saisie" is "date d'effet", it is an immediate transfer
                # deferred transfers will be handle on another page with more information
                return Date(CleanText(TableCell("exec_date")), dayfirst=True)(self) == Date(
                    CleanText(TableCell("_created_date")), dayfirst=True
                )(self)

            obj_currency = "EUR"
            obj_exec_date = Date(CleanText(TableCell("exec_date")), dayfirst=True)
            obj_amount = CleanDecimal.US(TableCell("amount"))
            # will be used after to try to get some information on the recipient and emitter account
            obj__recipient_name = CleanText(TableCell("_rcpt_name"))
            obj_date_type = TransferDateType.FIRST_OPEN_DAY


class ValidateTransferPage(LoggedPage, HTMLPage):
    is_here = '//p[contains(text(), "votre code confidentiel")]'

    def get_element_by_name(self, col_heads_name):
        # self.col_heads and self.col_contents have to be defined to use this function

        assert len(self.col_heads) > 0
        # self.col_heads and self.col_contents should have same length
        assert len(self.col_heads) == len(self.col_contents)

        for index, head in enumerate(self.col_heads):
            if col_heads_name in head:
                return self.col_contents[index]
        assert False

    def handle_response(self, account, recipient, amount, reason):
        tables_xpath = '//table[@id="table-confVrt" or @id="table-confDestinataire"]'

        # Summary is divided into 2 tables, we have to concat them
        # col_heads is a list of all header of the 2 tables (order is important)
        self.col_heads = [CleanText(".")(head) for head in self.doc.xpath(tables_xpath + '//td[@class="libColumn"]')]
        # col_contents is a list of all content of the 2 tables (order is important)
        self.col_contents = [
            CleanText(".")(content) for content in self.doc.xpath(tables_xpath + '//td[@class="contentColumn"]')
        ]

        transfer = Transfer()

        transfer.currency = Currency().filter(self.get_element_by_name("Montant"))
        transfer.amount = CleanDecimal().filter(self.get_element_by_name("Montant"))

        date = Regexp(pattern=r"(\d+/\d+/\d+)").filter(self.get_element_by_name("Date du virement"))
        transfer.exec_date = Date(dayfirst=True).filter(date)

        account_label_id = self.get_element_by_name("Compte à débiter")
        transfer.account_id = Regexp(pattern=r"(\d+)").filter(account_label_id)
        transfer.account_label = Regexp(pattern=r"([\w \.]+)").filter(account_label_id)
        # account iban is not in the summary page
        transfer.account_iban = account.iban

        transfer.recipient_id = recipient.id
        transfer.recipient_iban = self.get_element_by_name("IBAN").replace(" ", "")
        transfer.recipient_label = self.get_element_by_name("Nom du bénéficiaire")
        transfer.label = CleanText('//table[@id="table-confLibelle"]//p')(self.doc)

        return transfer

    def get_password(self, password):
        img_src = CleanText('//div[@id="paveNumTrans"]//img[contains(@id, "imagePave")]/@src')(self.doc)
        f = BytesIO(self.browser.open(img_src).content)

        vk = TransferVirtualKeyboard(
            file=f, cols=8, rows=3, matching_symbols=string.ascii_lowercase[: 8 * 3], browser=self.browser
        )

        return vk.get_string_code(password)

    def validate_transfer(self, password):
        # need only the 5 first characters of password to validate transfer
        formatted_password = self.get_password(password[:5])
        form = self.get_form(xpath='//div[@id="paveNumTrans"]/parent::form')

        # Get validation btn id because '_idJsp27' part may be not stable
        validation_btn_id = CleanText('//div[@id="paveNumTrans"]//input[contains(@id, "boutonValider")]/@id')(self.doc)

        form["codepasse"] = formatted_password
        form["motDePasse"] = formatted_password
        form[validation_btn_id] = ""
        form.submit()


class ConfirmTransferPage(LoggedPage, HTMLPage):
    def on_load(self):
        error_msg = '//p[@id="messErreur"]/span'
        if self.doc.xpath(error_msg):
            raise TransferBankError(message=CleanText(error_msg)(self.doc))

        confirm_transfer_xpath = '//h2[contains(text(), "Virement enregistr")]'
        assert self.doc.xpath(confirm_transfer_xpath)


class BaseScheduledTransferElement(ItemElement):
    klass = Transfer

    obj_recipient_label = CleanText('./td[@class="destinataire"]')
    obj_amount = CleanDecimal.US('./td[@class="montant"]')
    obj_account_id = CleanText('./td[@class="numCompteEmetteur"]')
    obj_exec_date = Date(CleanText('./td[@class="dateEffet"]'), dayfirst=True)

    obj_label = CleanText("./preceding-sibling::tr[2]//p/text()")
    obj_id = Regexp(Attr("./following-sibling::tr[1]//a[1]", "onclick"), r"'virNumOperation','(\d+)'")
    obj_currency = Currency(
        Regexp(CleanText('./preceding-sibling::tr[1]//td[contains(@class, "montant")]'), r"Montant \((.+)\)")
    )
    obj__unparsed_js_args = Attr("./following-sibling::tr[1]//a[1]", "onclick")


class ScheduledTransfersPage(LoggedPage, HTMLPage):
    def js2args(self, s):
        args = {}
        for sub in re.findall(r"\['([^']+)','([^']+)'\]", s):
            args[sub[0]] = sub[1]

        sub = re.search(r"oamSubmitForm.+?,\'([^:]+).([^\']+)", s)
        args["%s:_idcl" % sub.group(1)] = f"{sub.group(1)}:{sub.group(2)}"
        args["%s_SUBMIT" % sub.group(1)] = 1
        args["_form_name"] = sub.group(1)

        return args

    def iter_transfers(self):
        return chain(self.iter_periodic_transfers(), self.iter_deferred_transfers())

    @method
    class iter_periodic_transfers(ListElement):
        item_xpath = '//table[@id="table-virements-en-cours"]//tr[@class="ligne1"]'

        class item(BaseScheduledTransferElement):
            obj_date_type = TransferDateType.PERIODIC

    @method
    class iter_deferred_transfers(ListElement):
        item_xpath = '//table[@id="table-virements-en-attente"]//tr[@class="ligne1"]'

        class item(BaseScheduledTransferElement):
            obj_date_type = TransferDateType.DEFERRED

    def open_transfer_page(self, unparsed_js_args):
        js_args = self.js2args(unparsed_js_args)
        form = self.get_form(name=js_args["_form_name"])
        form.update(js_args)
        # instead of using Form.submit, we just use the form's request to avoid the useless browser.location
        # otherwise, after each transfer filling we would have to locate back to the transfers list page
        return self.browser.open(form.request).page


class ScheduledTransferDetailsPage(HTMLPage, LoggedPage):
    def fill_scheduled_transfer(self, obj):
        self._fill_common_scheduled(obj=obj)
        if obj.date_type == TransferDateType.PERIODIC:
            self._fill_periodic(obj=obj)
        # no details specific to deferred transfers

    @method
    class _fill_common_scheduled(ItemElement):
        obj_account_label = CleanText('//table[@id="tableVirt1"]//td[@class="intituleCompte"]')
        obj__rcpt_name = CleanText(
            '//table[@id="tableVirt2"]//td[text()="Nom du bénéficiaire :"]/following-sibling::td'
        )
        obj__acc_name = CleanText('//table[@id="tableVirt2"]//td[text()="Nom du compte :"]/following-sibling::td')

        # constructed as in iter_recipients
        obj_recipient_label = Format("%s - %s", Field("_acc_name"), Field("_rcpt_name"))
        obj_recipient_iban = CleanText('//table[@id="tableVirt2"]//td[text()="IBAN :"]/following-sibling::td')

    @method
    class _fill_periodic(ItemElement):
        FREQ_LABELS = {
            "Mensuelle": TransferFrequency.MONTHLY,
            "Trimestrielle": TransferFrequency.QUARTERLY,
            "Semestrielle": TransferFrequency.SEMIANNUALLY,
            "Annuelle": TransferFrequency.YEARLY,
        }

        obj_last_due_date = Date(CleanText('//table[@id="tableVirt3"]//td[@class="fin"]'), dayfirst=True)
        obj_frequency = Map(
            CleanText('//table[@id="tableVirt3"]//td[@class="libPeriodicite"]'), FREQ_LABELS, TransferFrequency.UNKNOWN
        )
