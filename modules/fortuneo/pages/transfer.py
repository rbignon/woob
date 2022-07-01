# -*- coding: utf-8 -*-

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

# flake8: compatible

from __future__ import unicode_literals

import re
from datetime import date, timedelta
from itertools import chain
from urllib.parse import parse_qs, urlparse

from woob.browser.pages import HTMLPage, PartialHTMLPage, LoggedPage
from woob.browser.elements import method, ListElement, ItemElement, TableElement
from woob.browser.filters.html import Attr, Link, TableCell
from woob.browser.filters.standard import (
    CleanText, Date, Regexp, CleanDecimal, Currency, Field, Env,
    Map, Base,
)
from woob.capabilities.bank import (
    Recipient, Transfer, TransferBankError, AddRecipientBankError,
    TransferStatus, TransferFrequency, TransferDateType, Emitter,
)
from woob.capabilities.base import NotAvailable
from woob.tools.json import json

from .accounts_list import ActionNeededPage


class RecipientsPage(ActionNeededPage):
    @method
    class iter_external_recipients(ListElement):
        # use list element because there are 4th for 7td in one tr
        item_xpath = '//div[@id="listeCompteExternes"]/table/tbody//tr[@class="ct"]'

        def condition(self):
            return 'Aucun compte externe enregistré' not in CleanText('.')(self)

        class item(ItemElement):
            klass = Recipient

            def obj_label(self):
                if Field('_custom_label')(self):
                    return '{} - {}'.format(Field('_recipient_name')(self), Field('_custom_label')(self))
                return Field('_recipient_name')(self)

            def obj_id(self):
                recipient_id = Regexp(CleanText('./td[3]/input[1]/@id'), r'(?<=ribFormate_compte_)(.*)')(self)
                return recipient_id

            obj__recipient_name = CleanText('./td[2]')
            obj__custom_label = CleanText('./td[4]')
            obj_iban = NotAvailable
            obj_category = 'Externe'
            obj_enabled_at = date.today()
            obj_currency = 'EUR'
            obj_bank_name = CleanText('./td[1]')

    def check_external_iban_form(self, recipient):
        form = self.get_form(id='CompteExterneActionForm')
        form['codePaysBanque'] = recipient.iban[:2]
        form['codeIban'] = recipient.iban
        form.url = self.browser.BASEURL + '/fr/prive/verifier-compte-externe.jsp'
        form.submit()

    def check_recipient_iban(self):
        if not CleanText('//input[@name="codeBic"]/@value')(self.doc):
            raise AddRecipientBankError(message="Le bénéficiaire est déjà présent ou bien l'iban est incorrect")

    def fill_recipient_form(self, recipient):
        form = self.get_form(id='CompteExterneActionForm')
        form['codePaysBanque'] = recipient.iban[:2]
        form['codeIban'] = recipient.iban
        form['libelleCompte'] = recipient.label
        form['nomTitulaireCompte'] = recipient.label
        form['methode'] = 'verifierAjout'
        form.submit()

    def get_new_recipient(self, recipient):
        recipient_xpath = '//form[@id="CompteExterneActionForm"]//ul'

        rcpt = Recipient()
        rcpt.label = Regexp(
            CleanText(
                recipient_xpath + '/li[contains(text(), "Nom du titulaire")]',
                replace=[(' ', '')]
            ),
            r'(?<=Nomdutitulaire:)(\w+)'
        )(self.doc)
        rcpt.iban = Regexp(
            CleanText(
                recipient_xpath + '/li[contains(text(), "IBAN")]'
            ),
            r'IBAN : ([A-Za-z]{2}[\dA-Za-z]+)'
        )(self.doc)
        rcpt.id = rcpt.iban
        rcpt.category = 'Externe'
        rcpt.enabled_at = date.today() + timedelta(1)
        rcpt.currency = 'EUR'
        return rcpt

    def get_error(self):
        return CleanText('//div[@class="erreur_texte"]/p[1]')(self.doc)

    def get_send_code_form(self):
        form = self.get_form(id='CompteExterneActionForm')
        if not form.url:
            # Means we have an app validation, but we can still ask for sms.
            # This method just retrieve the url of the form because it is
            # hidden in the javascript.
            form['methode'] = 'verifierAjout'
            form['fallbackSMS'] = True

            js_text = CleanText('//script[contains(text(), "OTP")]')(self.doc)
            # There are multiple urls in the javascript, so we want to make sure we
            # match the right one everytime to avoid sending an incorrect form.
            urls = re.findall(r'OTP\(\){[^}]+"action", "([^"]+)', js_text)
            if not len(urls):
                raise AssertionError("Should have matched at least one URL for new recipient sms form")
            elif len(urls) > 1:
                raise AssertionError("Should not have matched multiple URLs for new recipient sms form")
            form.url = urls[0]
        return form


class ConfirmRecipientPage(LoggedPage, PartialHTMLPage):
    def on_load(self):
        if not self.doc.xpath('//input[@id="otp"]') and not self.doc.xpath('//div[@class="confirmationAjoutCompteExterne"]'):
            raise AddRecipientBankError(
                message=CleanText('//div[@id="aidesecuforte"]/p[contains("Nous vous invitons")]')(self.doc)
            )

    def build_doc(self, content):
        return super().build_doc(b'<form>' + content + b'</form>')

    def is_code_expired(self):
        return self.doc.xpath('//label[contains(text(), "Le code sécurité est expiré. Veuillez saisir le nouveau code reçu")]')

    def rcpt_after_sms(self):
        return self.doc.xpath(
            '//div[@class="confirmationAjoutCompteExterne"]'
            + '/h2[contains(text(), "ajout de compte externe a bien été prise en compte")]'
        )

    def get_error(self):
        return CleanText(
            '//form//p[@class="container error"]//label[@class="error"]'
        )(self.doc)


class OTPSMSPage(LoggedPage, PartialHTMLPage):
    def get_send_code_form(self):
        return self.get_form()

    def build_doc(self, content):
        return super().build_doc(b'<form>' + content + b'</form>')

    def get_phone_number(self):
        return Regexp(
            CleanText('//span[@id="secu_forte_otp_padding_left"]'),
            r'code sécurité au ([0+].+?)\.',
        )(self.doc).strip()


class RegisterTransferPage(LoggedPage, HTMLPage):
    @method
    class fill_tpp_account_id(ItemElement):
        def obj__tpp_id(self):
            accounts_list = Regexp(
                CleanText('//script[contains(text(), "listeComptesADebiter")]'),
                r'listeComptesADebiter = (.*}]); var listeComptesACrediter',
                default='[]'
            )(self)
            accounts_list = json.loads(accounts_list)
            for account in accounts_list:
                if account['numero'] == self.obj.id:
                    return account.get('numeroContratTopaze', NotAvailable)
            return NotAvailable

    @method
    class iter_internal_recipients(ListElement):
        item_xpath = '//select[@name="compteACrediter"]/option[not(@selected)]'

        class item(ItemElement):
            klass = Recipient

            obj_id = CleanText('./@value')
            obj_iban = NotAvailable
            obj_label = CleanText('.')
            obj__recipient_name = CleanText('.')
            obj_category = 'Interne'
            obj_enabled_at = date.today()
            obj_currency = 'EUR'
            obj_bank_name = 'FORTUNEO'

            def condition(self):
                # external recipient id contains 43 characters
                return len(Field('id')(self)) < 40 and Env('origin_account_id')(self) != Field('id')(self)

    @method
    class iter_emitters(ListElement):
        item_xpath = '//select[@name="compteADebiter"]/option[not(@selected)]'

        class item(ItemElement):
            klass = Emitter

            obj_id = CleanText('./@value')
            obj_currency = 'EUR'

            def obj_label(self):
                return re.sub(self.obj_id(self), '', CleanText('.')(self)).strip()

    def is_account_transferable(self, origin_account):
        for account in self.doc.xpath('//select[@name="compteADebiter"]/option[not(@selected)]'):
            if origin_account.id in CleanText('.')(account):
                return True
        return False

    def get_recipient_transfer_id(self, recipient):
        for account in self.doc.xpath('//select[@name="compteACrediter"]/option[not(@selected)]'):
            recipient_transfer_id = CleanText('./@value')(account)

            if (
                recipient.id == recipient_transfer_id
                or recipient.id in CleanText('.', replace=[(' ', '')])(account)
            ):
                return recipient_transfer_id

        # Sometimes, we obtained the equivalent of 'hashRib' in the recipients
        # list on the page, but we actually need the 'hashIban'. We need to get
        # the correspondances table from the embedded Javascript code, then
        # try the other code.
        for script_tag in self.doc.xpath(
            '//script[contains(., "var listeComptesACrediter")]',
        ):
            raw_creditor_list = Regexp(
                CleanText('.'),
                r'var listeComptesACrediter = (.+?}\]);',
                default=None,
            )(script_tag)

            try:
                creditor_list = json.loads(raw_creditor_list)
            except ValueError:
                continue

            for creditor in creditor_list:
                if 'hashRib' in creditor and creditor['hashRib'] == recipient.id:
                    return creditor['hashIban']

    def fill_transfer_form_and_get_used_recipient_id(self, account, recipient, amount, label, exec_date):
        """
        The used recipient transfer ID can be different from the one stored inside the recipient params, in the case where
        the recipient ID is a hashRib, we need to give the hashIban that is fetched from an association table.
        In order to allow sanity check later on during the transfer execution process, we return the used recipient ID
        to make sure it is not changed in between pages.
        """
        recipient_transfer_id = self.get_recipient_transfer_id(recipient)
        # We make sure that we got an actual recipient ID
        # If it's not the case, we cannot go further
        assert recipient_transfer_id

        form = self.get_form(id='SaisieVirementForm')
        form['compteADebiter'] = account.id
        form['libelleCompteADebiter'] = CleanText(
            '//select[@name="compteADebiter"]/option[@value="%s"]' % account.id
        )(self.doc)
        form['compteACrediter'] = recipient_transfer_id
        form['libelleCompteACrediter'] = CleanText(
            '//select[@name="compteACrediter"]/option[@value="%s"]' % recipient_transfer_id
        )(self.doc)
        form['nomBeneficiaire'] = recipient._recipient_name
        form['libellePopupDoublon'] = recipient._recipient_name
        form['destinationEconomiqueFonds'] = ''
        form['periodicite'] = 1
        form['typeDeVirement'] = 'VI'
        form['dateDeVirement'] = exec_date.strftime('%d/%m/%Y')
        form['montantVirement'] = amount
        form['libelleVirementSaisie'] = label.encode(self.encoding, errors='xmlcharrefreplace').decode(self.encoding)
        form.submit()

        return recipient_transfer_id


class ValidateTransferPage(LoggedPage, HTMLPage):
    def on_load(self):
        errors_msg = (
            CleanText('//form[@id="SaisieVirementForm"]/p[has-class("error")]/label')(self.doc),  # may be deprecated
            CleanText(
                '//div[@id="error" and @class="erreur_texte"]/p[contains(text(), "n\'est pas autorisé")]'
            )(self.doc),
            CleanText('//form[@id="SaisieVirementForm"]//label[has-class("error")]')(self.doc),
            CleanText('//div[@id="error"]/p[@class="erreur_texte1"]')(self.doc),
        )

        for error in errors_msg:
            if error:
                raise TransferBankError(message=error)

        other_error_msg = self.doc.xpath('//div[@id="error" and @class="erreur_texte"]')
        assert not other_error_msg, 'Error "other_error_msg" is not handled yet'

    def check_transfer_data(self, transfer_data):
        for t_data in transfer_data:
            assert t_data in transfer_data[t_data], ('{} not found in transfer summary {}'
                                                     .format(t_data, transfer_data[t_data]))

    def handle_response(self, account, recipient, amount, label, exec_date, used_recipient_id):
        summary_xpath = '//div[@id="as_verifVirement.do_"]//ul'
        transfer_form = self.get_form(id='SaisieVirementForm')

        transfer = Transfer()

        transfer_data = {
            account.id: CleanText(
                summary_xpath + '/li[contains(text(), "Compte à débiter")]'
            )(self.doc),
            # For recipient ID we check that the ID (hashIban) hasn't changed between pages
            # The value displayed to the user is an obfuscated IBAN, not a hashIban
            # So we get the value from the real hidden form instead of the user-friendly div
            #
            # We cannot match the hashRib to the hashIban the same way as on the
            # transfer_page, as the correspondance table is no longer present here.
            used_recipient_id: transfer_form.get('compteACrediter'),
            recipient._recipient_name: CleanText(
                summary_xpath + '/li[contains(text(), "Nom du bénéficiaire")]'
            )(self.doc),
            label: CleanText(summary_xpath + '/li[contains(text(), "Motif")]')(self.doc),
        }
        self.check_transfer_data(transfer_data)

        transfer.account_id = account.id
        transfer.account_label = account.label
        transfer.account_iban = account.iban

        # The hashrib is stored in the transfer (not hashiban) because this is the hashrib we
        # get in the iter recipient
        transfer.recipient_id = recipient.id
        transfer.recipient_label = recipient.label
        transfer.recipient_iban = recipient.iban

        transfer.label = label
        transfer.currency = Currency(summary_xpath + '/li[contains(text(), "Montant")]')(self.doc)
        transfer.amount = CleanDecimal(
            Regexp(CleanText(summary_xpath + '/li[contains(text(), "Montant")]'), r'((\d+)\.?(\d+)?)')
        )(self.doc)
        transfer.exec_date = Date(
            Regexp(
                CleanText(summary_xpath + '/li[contains(text(), "Date de virement")]'),
                r'(\d+/\d+/\d+)'),
            dayfirst=True
        )(self.doc)

        return transfer

    def validate_transfer(self):
        form = self.get_form(id='SaisieVirementForm')
        form['methode'] = 'valider'
        form.submit()


class ConfirmTransferPage(LoggedPage, HTMLPage):
    def build_doc(self, content):
        return super().build_doc(b'<form>' + content + b'</form>')

    def get_send_code_form(self):
        return self.get_form(id='SaisieVirementForm')

    def confirm_transfer(self):
        confirm_transfer_url = '/fr/prive/mes-comptes/compte-courant/realiser-operations/effectuer-virement/confirmer-saisie-virement.jsp'
        self.browser.location(self.browser.BASEURL + confirm_transfer_url, data={'operationTempsReel': 'true'})

    def transfer_confirmation(self, transfer):
        if self.doc.xpath('//div[@class="confirmation_virement"]/h2[contains(text(), "virement a bien été enregistrée")]'):
            return transfer
        raise AssertionError('Transfer confirmation message not found inside the transfer confirmation page')

    def is_code_expired(self):
        return self.doc.xpath('//label[contains(text(), "Le code sécurité est expiré. Veuillez saisir le nouveau code reçu")]')

    def get_error(self):
        return CleanText(
            '//form//p[@class="container error"]//label[@class="error"]'
        )(self.doc)


class BaseIterTransfers(TableElement):
    col_amount = 'Montant'
    col_recipient_label_iban = 'Compte à créditer'
    col_account_number_label = 'Compte à débiter'


class BaseTransferItem(ItemElement):
    klass = Transfer
    # emitter account and recipient are written like "<account label> <obfuscated iban>"
    IBAN_REGEXP = r'[A-Z]{2}\d{2} \d{4} (?:XXXX ){3}.+'

    def obj_id(self):
        activation_link = Link(self.get_status_element())(self)
        url_params = parse_qs(urlparse(activation_link).query)
        return url_params['idOpe'][0]

    obj_amount = CleanDecimal.French(TableCell('amount'))
    obj_recipient_label = Regexp(CleanText(TableCell('recipient_label_iban')), r'(.*) {}'.format(IBAN_REGEXP))
    obj_account_label = Regexp(CleanText(TableCell('account_number_label')), r'N° \d+ (.*)')


class TransferListPage(LoggedPage, HTMLPage):
    # immediate and instant transfers are not displayed...
    def iter_transfers(self):
        return chain(self.iter_periodic_transfers(), self.iter_deferred_transfers())

    @method
    class iter_deferred_transfers(BaseIterTransfers):
        head_xpath = '//table[@id="tablePonctuelle"]/thead/tr/th'
        item_xpath = '//table[@id="tablePonctuelle"]//tbody/tr[td]'

        col_date = 'Date'

        class DeferredTransferItem(BaseTransferItem):
            # not proud of this one but there is more td than th in the table, the status element has no
            # matching column in headers
            def get_status_element(self):
                return Base(TableCell('amount'), './following-sibling::td/a')

            # the transfer is not displayed when it is done or canceled. So it can only be scheduled here...
            obj_status = TransferStatus.SCHEDULED
            obj_date_type = TransferDateType.DEFERRED
            obj_exec_date = Date(CleanText(TableCell('date')), dayfirst=True)

    @method
    class iter_periodic_transfers(BaseIterTransfers):
        head_xpath = '//table[@id="ope_per"]/thead/tr/th'
        item_xpath = '//table[@id="ope_per"]//tbody/tr[td]'

        col_frequency = 'Périodicité'
        col_type = 'Type'

        class PeriodicTransferItem(BaseTransferItem):
            FREQUENCY_MAPPING = {
                'Mensuelle': TransferFrequency.MONTHLY,
                'Trimestrielle': TransferFrequency.QUARTERLY,
                'Semestrielle': TransferFrequency.SEMIANNUALLY,
                'Annuelle': TransferFrequency.YEARLY,
            }

            # not proud of this one but there is more td than th in the table, the status element has no
            # matching column in headers
            def get_status_element(self):
                return Base(TableCell('frequency'), './following-sibling::td/a[2]')

            def condition(self):
                is_operation_active = Attr(self.get_status_element(), 'class')(self) == 'icon_feu_vert'
                return CleanText(TableCell('type'))(self) == 'Vir' and is_operation_active

            obj_frequency = Map(CleanText(TableCell('frequency')), FREQUENCY_MAPPING, TransferFrequency.UNKNOWN)

            obj_date_type = TransferDateType.PERIODIC
