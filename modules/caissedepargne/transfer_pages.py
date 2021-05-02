# -*- coding: utf-8 -*-

# Copyright(C) 2012 Romain Bignon
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
from datetime import datetime

from lxml import html

from woob.browser.elements import ItemElement, ListElement, SkipItem, TableElement, method
from woob.browser.filters.html import Attr, Link, TableCell
from woob.browser.filters.standard import (
    Base, CleanDecimal, CleanText, Currency, Date, Env, Field, MapIn, Regexp, Upper,
)
from woob.browser.pages import HTMLPage, LoggedPage
from woob.capabilities.bank import (
    Account, AddRecipientBankError, Emitter, EmitterNumberType, Recipient, Transfer, TransferBankError,
    TransferDateType, TransferFrequency, TransferStatus,
)
from woob.capabilities.base import NotAvailable
from woob.tools.capabilities.bank.iban import is_iban_valid, rib2iban
from woob.tools.capabilities.bank.transactions import FrenchTransaction
from woob.tools.compat import unicode

from .base_pages import fix_form
from .pages import IndexPage


class CheckingPage(LoggedPage, HTMLPage):
    def is_here(self):
        account_columns_here = [
            self.doc.xpath("//th[text()='Nature']"),
            self.doc.xpath("//th[text()='N°']"),
            self.doc.xpath("//th[text()='Titulaire']"),
            self.doc.xpath("//th[text()='Solde']"),
        ]
        return all(account_columns_here)

    def go_transfer_list(self):
        form = self.get_form(id='main')

        form['__EVENTARGUMENT'] = 'HISVIR0&codeMenu=WVI3'
        form['__EVENTTARGET'] = 'MM$Menu_Ajax'

        fix_form(form)
        form.submit()

    def go_subscription(self):
        form = self.get_form(id='main')
        form['m_ScriptManager'] = 'MM$m_UpdatePanel|MM$Menu_Ajax'
        form['__EVENTTARGET'] = 'MM$Menu_Ajax'
        link = Link('//a[contains(@title, "e-Documents") or contains(@title, "Relevés en ligne")]')(self.doc)
        form['__EVENTARGUMENT'] = re.search(r'Ajax", "(.*)", true', link).group(1)
        form.submit()


FILLING_XPATH = '//td[span[text()="%s"]]/following-sibling::td'


class TransferListPage(LoggedPage, HTMLPage):
    is_here = '//h2[text()="Suivre mes virements"]'

    @method
    class iter_transfers(TableElement):
        head_xpath = '//table[@summary="Liste des RICE à imprimer"]//th'
        item_xpath = '//table[@summary="Liste des RICE à imprimer"]//tr[td]'

        col_amount = 'Montant'
        col_recipient_label = 'Bénéficiaire'
        col_label = 'Référence'
        col_date = 'Date'

        class item(ItemElement):
            klass = Transfer

            obj_amount = CleanDecimal.French(TableCell('amount'))
            obj_recipient_label = CleanText(TableCell('recipient_label'))
            obj_label = CleanText(TableCell('label'))
            obj_exec_date = Date(CleanText(TableCell('date')), dayfirst=True)
            obj__formarg = Regexp(
                Base(TableCell('label'), Link('./a')),
                r'WebForm_PostBackOptions\(".+?", "(.+?)"',
            )

            obj__status_text = CleanText('(./ancestor::table/parent::div/preceding-sibling::h3)[last()]')

            STATUS_LABELS = {
                "Virement(s) en attente d'exécution": TransferStatus.SCHEDULED,
                "Virement(s) exécuté(s)": TransferStatus.DONE,
                "Virement(s) refusé(s)": TransferStatus.CANCELLED,
                "Virement(s) annulé(s) ou en cours d'annulation": TransferStatus.CANCELLED,
                "Virement(s) Permanent(s)": TransferStatus.SCHEDULED,
            }

            obj_status = MapIn(obj__status_text, STATUS_LABELS, TransferStatus.UNKNOWN)

    def open_transfer(self, formarg):
        form = self.get_form(id='main')
        form['__EVENTARGUMENT'] = formarg
        form['__EVENTTARGET'] = 'MM$HISTORIQUE_VIREMENTS'
        fix_form(form)
        form.submit()

    def fill_transfer(self, obj):
        self._fill_common_transfer(obj=obj)
        if obj._is_periodic:
            self._fill_periodic(obj=obj)
        else:
            self._fill_single(obj=obj)

    @method
    class _fill_common_transfer(ItemElement):
        def get_value(self, label):
            return CleanText(self.td_xpath % label)(self)

        # example (first_open_day): <number>
        # example (deferred or periodic): <number> - <another number>
        obj_id = CleanText(FILLING_XPATH % 'N° du virement', symbols=' ')

        # example: "CD dépot - <account id>"
        obj_account_id = Regexp(
            CleanText(FILLING_XPATH % 'Compte à débiter'),
            r' - (.+?)$',
        )

        # internal can be "<account label> - <account id>"
        # external can be "EXT - <iban>" or "C.CHEQUE - <iban>" or "<iban>"
        obj__rcpt_value = Regexp(
            CleanText(FILLING_XPATH % 'Compte à créditer'),
            r'^(?:.*- )?(.+?)$',
        )

        def obj_recipient_iban(self):
            value = Field('_rcpt_value')(self)
            if is_iban_valid(value):
                return value

        def obj_recipient_id(self):
            value = Field('_rcpt_value')(self)
            if not is_iban_valid(value):
                return value

        def obj__is_periodic(self):
            return bool(CleanText(FILLING_XPATH % 'Périodicité')(self))

    @method
    class _fill_single(ItemElement):
        obj_creation_date = Date(
            Regexp(
                # if you're wondering "what's the difference with FILLING_XPATH?"
                # they didn't put a <span> in it...
                CleanText('//td[normalize-space(text())="Date(s)"]/following-sibling::td'),
                r"Demandé le (\d{2}/\d{2}/\d{4})",
            ),
            dayfirst=True,
        )

        def obj_date_type(self):
            if self.obj.status == TransferStatus.DONE:
                # FIXME is it marked as done if submitting it on a sunday?
                return TransferDateType.FIRST_OPEN_DAY
            return TransferDateType.DEFERRED

    @method
    class _fill_periodic(ItemElement):
        FREQ_LABELS = {
            'Hebdomadaire': TransferFrequency.WEEKLY,
            'Mensuelle': TransferFrequency.MONTHLY,
            'Trimestrielle': TransferFrequency.QUARTERLY,
            'Semestrielle': TransferFrequency.BIANNUAL,
            'Annuelle': TransferFrequency.YEARLY,
        }

        obj_first_due_date = Date(
            CleanText('//td[normalize-space(text())="Date de première échéance"]/following-sibling::td'),
            dayfirst=True,
        )
        obj_last_due_date = Date(CleanText(FILLING_XPATH % "Date de dernière échéance"), dayfirst=True)
        obj_frequency = MapIn(CleanText(FILLING_XPATH % "Périodicité"), FREQ_LABELS)
        obj__etat = CleanText(FILLING_XPATH % "Etat du virement")

        obj_date_type = TransferDateType.PERIODIC


class TransferErrorPage(object):
    def on_load(self):
        errors_xpaths = [
            '//div[h2[text()="Information"]]/p[contains(text(), "Il ne pourra pas être crédité avant")]',
            '//span[@id="MM_LblMessagePopinError"]/p | //div[h2[contains(text(), "Erreur de saisie")]]/p[1] | //span[@class="error"]/strong',
            '//div[@id="MM_m_CH_ValidationSummary" and @class="MessageErreur"]',
        ]

        for error_xpath in errors_xpaths:
            error = CleanText(error_xpath)(self.doc)
            if error:
                raise TransferBankError(message=error)


class MyRecipient(ItemElement):
    klass = Recipient

    # Assume all recipients currency is euros.
    obj_currency = 'EUR'

    def obj_enabled_at(self):
        return datetime.now().replace(microsecond=0)


class MyEmitter(ItemElement):
    klass = Emitter

    obj_id = Attr('.', 'value')
    obj_currency = Currency('.')
    obj_number_type = EmitterNumberType.IBAN

    def obj_number(self):
        return rib2iban(Attr('.', 'value')(self))


class MyEmitters(ListElement):
    item_xpath = '//select[@id="MM_VIREMENT_SAISIE_VIREMENT_ddlCompteDebiter"]/option'

    class Item(MyEmitter):
        pass


class MyRecipients(ListElement):
    def parse(self, obj):
        self.item_xpath = self.page.RECIPIENT_XPATH

    class Item(MyRecipient):
        def validate(self, obj):
            return self.obj_id(self) != self.env['account_id']

        obj_id = Env('id')
        obj_iban = Env('iban')
        obj_bank_name = Env('bank_name')
        obj_category = Env('category')
        obj_label = Env('label')

        def parse(self, el):
            value = Attr('.', 'value')(self)
            # Autres comptes
            if value in ('AC', 'AC_SOL'):
                raise SkipItem()

            if value[0] == 'I':
                self.env['category'] = 'Interne'
            else:
                self.env['category'] = 'Externe'

            if self.env['category'] == 'Interne':
                # TODO use after 'I'?
                _id = Regexp(CleanText('.'), r'- (\w+\d\w+)')(self)  # at least one digit
                accounts = list(self.page.browser.get_accounts_list()) + list(self.page.browser.get_loans_list())
                # If it's an internal account, we should always find only one account with _id in it's id.
                # Type card account contains their parent account id, and should not be listed in recipient account.
                match = [acc for acc in accounts if _id in acc.id and acc.type != Account.TYPE_CARD]
                assert len(match) == 1
                match = match[0]
                self.env['id'] = match.id
                self.env['iban'] = match.iban
                self.env['bank_name'] = u"Caisse d'Épargne"
                self.env['label'] = match.label
            # Usual case `E-` or `UE-`
            elif value[1] == '-' or value[2] == '-':
                full = CleanText('.')(self)
                if full.startswith('- '):
                    self.logger.warning('skipping recipient without a label: %r', full)
                    raise SkipItem()

                # <recipient name> - <account number or iban> - <bank name (optional)>
                # bank name can have one dash, multiple dots in their names or just be a dash (seen in palatine, example below)
                # eg: ING-DiBan / C.PROF. / B.R.E.D
                # Seen in palatine (the bank name can be a dash): <recipient name> - <iban> - -
                mtc = re.match(r'(?P<label>.+) - (?P<id>[^-]+) - ?(?P<bank>[^-]+-?[\w\. ]+)?-?$', full)
                assert mtc, "Unhandled recipient's label/iban/bank name format"
                self.env['id'] = self.env['iban'] = mtc.group('id')
                self.env['bank_name'] = (mtc.group('bank') and mtc.group('bank').strip()) or NotAvailable
                self.env['label'] = mtc.group('label')
            # Fcking corner case
            else:
                # former regex: '(?P<id>.+) - (?P<label>[^-]+) -( [^-]*)?-?$'
                # the strip is in case the string ends by ' -'
                mtc = CleanText('.')(self).strip(' -').split(' - ')
                # it needs to contain, at least, the id and the label
                assert len(mtc) >= 2
                self.env['id'] = mtc[0]
                self.env['iban'] = NotAvailable
                self.env['bank_name'] = NotAvailable
                self.env['label'] = mtc[1]


class RecipientPage(LoggedPage, HTMLPage):
    EVENTTARGET = 'MM$WIZARD_AJOUT_COMPTE_EXTERNE'
    FORM_FIELD_ADD = 'MM$WIZARD_AJOUT_COMPTE_EXTERNE$COMPTE_EXTERNE_ADD'

    def on_load(self):
        error = CleanText('//span[@id="MM_LblMessagePopinError"]')(self.doc)
        if error:
            raise AddRecipientBankError(message=error)

    def is_here(self):
        return bool(CleanText('''
            //h2[contains(text(), "Ajouter un compte bénéficiaire")]
            | //h2[contains(text(), "Confirmer l\'ajout d\'un compte bénéficiaire")]
        ''')(self.doc))

    def post_recipient(self, recipient):
        form = self.get_form(id='main')
        form['__EVENTTARGET'] = '%s$m_WizardBar$m_lnkNext$m_lnkButton' % self.EVENTTARGET
        form['%s$m_RibIban$txtTitulaireCompte' % self.FORM_FIELD_ADD] = recipient.label
        for i in range(len(recipient.iban) // 4 + 1):
            form['%s$m_RibIban$txtIban%s' % (self.FORM_FIELD_ADD, str(i + 1))] = recipient.iban[4 * i:4 * i + 4]
        form.submit()

    def confirm_recipient(self):
        form = self.get_form(id='main')
        form['__EVENTTARGET'] = 'MM$WIZARD_AJOUT_COMPTE_EXTERNE$m_WizardBar$m_lnkNext$m_lnkButton'
        form.submit()


class ProAddRecipientOtpPage(IndexPage):
    def on_load(self):
        error = CleanText('//div[@id="MM_m_CH_ValidationSummary" and @class="MessageErreur"]')(self.doc)
        if error:
            raise AddRecipientBankError(message='Wrongcode, ' + error)

    def is_here(self):
        return self.need_auth() and self.doc.xpath('//span[@id="MM_ANR_WS_AUTHENT_ANR_WS_AUTHENT_SAISIE_lblProcedure1"]')

    def set_browser_form(self):
        form = self.get_form(id='main')
        form['__EVENTTARGET'] = 'MM$ANR_WS_AUTHENT$m_WizardBar$m_lnkNext$m_lnkButton'
        self.browser.recipient_form = dict((k, v) for k, v in form.items())
        self.browser.recipient_form['url'] = form.url

    def get_prompt_text(self):
        return CleanText('////span[@id="MM_ANR_WS_AUTHENT_ANR_WS_AUTHENT_SAISIE_lblProcedure1"]')(self.doc)


class ProAddRecipientPage(RecipientPage):
    EVENTTARGET = 'MM$WIZARD_AJOUT_COMPTE_TIERS'
    FORM_FIELD_ADD = 'MM$WIZARD_AJOUT_COMPTE_TIERS$COMPTES_TIERS_ADD'

    def is_here(self):
        return CleanText('''
            //span[@id="MM_m_CH_lblTitle" and contains(text(), "Ajoutez un compte tiers")]
            | //span[@id="MM_m_CH_lblTitle" and contains(text(), "Confirmez votre ajout")]
        ''')(self.doc)


class TransferSummaryPage(TransferErrorPage, IndexPage):
    def is_here(self):
        return bool(CleanText('//h2[contains(text(), "Accusé de réception")]')(self.doc))

    def populate_reference(self, transfer):
        transfer.id = Regexp(CleanText('//p[contains(text(), "a bien été enregistré")]'), r'(\d+)')(self.doc)
        return transfer


class ProTransferSummaryPage(TransferErrorPage, IndexPage):
    def is_here(self):
        return bool(CleanText('//span[@id="MM_m_CH_lblTitle" and contains(text(), "Accusé de réception")]')(self.doc))

    def populate_reference(self, transfer):
        transfer.id = Regexp(
            CleanText('//span[@id="MM_VIREMENT_AR_VIREMENT_lblVirementEnregistre"]'),
            r'(\d+( - \d+)?)'
        )(self.doc)
        return transfer


class TransferPage(TransferErrorPage, IndexPage):
    RECIPIENT_XPATH = '//select[@id="MM_VIREMENT_SAISIE_VIREMENT_ddlCompteCrediter"]/option'

    def is_here(self):
        return bool(CleanText('//h2[contains(text(), "Effectuer un virement")]')(self.doc))

    def can_transfer(self, account):
        for o in self.doc.xpath('//select[@id="MM_VIREMENT_SAISIE_VIREMENT_ddlCompteDebiter"]/option'):
            if Regexp(CleanText('.'), r'- (\d+)')(o) in account.id:
                return True

    def get_origin_account_value(self, account):
        origin_value = [
            Attr('.', 'value')(o)
            for o in self.doc.xpath('//select[@id="MM_VIREMENT_SAISIE_VIREMENT_ddlCompteDebiter"]/option')
            if Regexp(CleanText('.'), r'- (\d+)')(o) in account.id
        ]
        assert len(origin_value) == 1, 'error during origin account matching'
        return origin_value[0]

    def get_recipient_value(self, recipient):
        if recipient.category == 'Externe':
            recipient_value = [
                Attr('.', 'value')(o)
                for o in self.doc.xpath(self.RECIPIENT_XPATH)
                if Regexp(CleanText('.'), r'.* - ([A-Za-z0-9]*) -', default=NotAvailable)(o) == recipient.iban
            ]
        elif recipient.category == 'Interne':
            recipient_value = [
                Attr('.', 'value')(o)
                for o in self.doc.xpath(self.RECIPIENT_XPATH)
                if (
                    Regexp(CleanText('.'), r'- (\d+)', default=NotAvailable)(o)
                    and Regexp(CleanText('.'), r'- (\d+)', default=NotAvailable)(o) in recipient.id
                )
            ]
        assert len(recipient_value) == 1, 'error during recipient matching'
        return recipient_value[0]

    def init_transfer(self, account, recipient, transfer):
        form = self.get_form(id='main')
        form['MM$VIREMENT$SAISIE_VIREMENT$ddlCompteDebiter'] = self.get_origin_account_value(account)
        form['MM$VIREMENT$SAISIE_VIREMENT$ddlCompteCrediter'] = self.get_recipient_value(recipient)
        form['MM$VIREMENT$SAISIE_VIREMENT$txtLibelleVirement'] = transfer.label
        form['MM$VIREMENT$SAISIE_VIREMENT$txtMontant$m_txtMontant'] = unicode(transfer.amount)
        form['__EVENTTARGET'] = 'MM$VIREMENT$m_WizardBar$m_lnkNext$m_lnkButton'
        if transfer.exec_date != datetime.today().date():
            form['MM$VIREMENT$SAISIE_VIREMENT$radioVirement'] = 'differe'
            form['MM$VIREMENT$SAISIE_VIREMENT$m_DateDiffere$txtDate'] = transfer.exec_date.strftime('%d/%m/%Y')
        form.submit()

    @method
    class iter_recipients(MyRecipients):
        pass

    def get_transfer_type(self):
        sepa_inputs = self.doc.xpath('//input[contains(@id, "MM_VIREMENT_SAISIE_VIREMENT_SEPA")]')
        intra_inputs = self.doc.xpath('//input[contains(@id, "MM_VIREMENT_SAISIE_VIREMENT_INTRA")]')

        assert not (len(sepa_inputs) and len(intra_inputs)), 'There are sepa and intra transfer forms'

        transfer_type = None
        if len(sepa_inputs):
            transfer_type = 'sepa'
        elif len(intra_inputs):
            transfer_type = 'intra'
        assert transfer_type, 'Sepa nor intra transfer form was found'
        return transfer_type

    def continue_transfer(self, origin_label, recipient_label, label):
        form = self.get_form(id='main')

        transfer_type = self.get_transfer_type()

        def fill(s, t):
            return s % (t.upper(), t.capitalize())

        form['__EVENTTARGET'] = 'MM$VIREMENT$m_WizardBar$m_lnkNext$m_lnkButton'
        form[fill('MM$VIREMENT$SAISIE_VIREMENT_%s$m_Virement%s$txtIdentBenef', transfer_type)] = recipient_label
        form[fill('MM$VIREMENT$SAISIE_VIREMENT_%s$m_Virement%s$txtIdent', transfer_type)] = origin_label
        form[fill('MM$VIREMENT$SAISIE_VIREMENT_%s$m_Virement%s$txtRef', transfer_type)] = label
        form[fill('MM$VIREMENT$SAISIE_VIREMENT_%s$m_Virement%s$txtMotif', transfer_type)] = label
        form.submit()

    def go_add_recipient(self):
        form = self.get_form(id='main')
        link = self.doc.xpath('//a[span[contains(text(), "Ajouter un compte bénéficiaire")]]')[0]
        m = re.search(
            r"PostBackOptions?\([\"']([^\"']+)[\"'],\s*['\"]([^\"']+)?['\"]",
            link.attrib.get('href', '')
        )
        form['__EVENTTARGET'] = m.group(1)
        form['__EVENTARGUMENT'] = m.group(2)
        form.submit()

    def handle_error(self):
        # the website cannot add recipients from out of France
        error_msg = CleanText('//div[@id="divPopinInfoAjout"]/p[not(a)]')(self.doc)
        if error_msg:
            raise AddRecipientBankError(message=error_msg)

    @method
    class iter_emitters(MyEmitters):

        class Item(MyEmitter):

            def obj_label(self):
                """
                Label looks like 'Mr Dupont Jean C.cheque - 52XXX87 + 176,12 €'.
                We only keep the first half (name and account name).
                What's left is: 'Mr Dupont Jean C.cheque'
                """
                raw_string = CleanText('.')(self)
                if '-' in raw_string:
                    return raw_string.split('-')[0]
                return raw_string

            def obj_balance(self):
                attribute_data = Attr('.', 'data-ce-html', default=None)(self)
                return CleanDecimal.French('//span')(html.fromstring(attribute_data))


class TransferConfirmPage(TransferErrorPage, IndexPage):
    def build_doc(self, content):
        # The page have some <wbr> tags in the label content (spaces added each 40 characters if the character is not a space).
        # Consequently the label can't be matched with the original one. We delete these tags.
        content = content.replace(b'<wbr>', b'')
        return super(TransferErrorPage, self).build_doc(content)

    def is_here(self):
        return bool(CleanText('//h2[contains(text(), "Confirmer mon virement")]')(self.doc))

    def confirm(self):
        form = self.get_form(id='main')
        form['__EVENTTARGET'] = 'MM$VIREMENT$m_WizardBar$m_lnkNext$m_lnkButton'
        form.submit()

    def update_transfer(self, transfer, account=None, recipient=None):
        """update `Transfer` object with web information to use transfer check"""

        # transfer informations
        transfer.label = (
            CleanText('.//tr[td[contains(text(), "Motif de l\'opération")]]/td[not(@class)]')(self.doc)
            or CleanText('.//tr[td[contains(text(), "Libellé")]]/td[not(@class)]')(self.doc)
            or CleanText('.//tr[th[contains(text(), "Libellé")]]/td[not(@class)]')(self.doc)
        )
        transfer.exec_date = Date(
            CleanText('.//tr[th[contains(text(), "En date du")]]/td[not(@class)]'),
            dayfirst=True
        )(self.doc)
        transfer.amount = CleanDecimal(
            '''
                .//tr[td[contains(text(), "Montant")]]/td[not(@class)]
                | .//tr[th[contains(text(), "Montant")]]/td[not(@class)]
            ''',
            replace_dots=True)(self.doc)
        transfer.currency = FrenchTransaction.Currency('''
            .//tr[td[contains(text(), "Montant")]]/td[not(@class)]
            | .//tr[th[contains(text(), "Montant")]]/td[not(@class)]
        ''')(self.doc)

        # recipient transfer informations, update information if there is no OTP SMS validation
        if recipient:
            transfer.recipient_label = recipient.label
            transfer.recipient_id = recipient.id

            if recipient.category == 'Externe':
                all_text = Upper(CleanText(
                    '''.//tr[th[contains(text(), "Compte à créditer")]]/td[not(@class)]'''
                ))(self.doc)

                for word in all_text.split():
                    if is_iban_valid(word):
                        transfer.recipient_iban = word
                        break
                else:
                    raise AssertionError('Unable to find IBAN (original was %s)' % recipient.iban)
            else:
                transfer.recipient_iban = recipient.iban

        # origin account transfer informations, update information if there is no OTP SMS validation
        if account:
            transfer.account_id = account.id
            transfer.account_iban = account.iban
            transfer.account_label = account.label
            transfer.account_balance = account.balance

        return transfer


class ProTransferConfirmPage(TransferConfirmPage):
    def is_here(self):
        return bool(CleanText('''
            //span[@id="MM_m_CH_lblTitle" and contains(text(), "Confirmez votre virement")]
        ''')(self.doc))

    def continue_transfer(self, origin_label, recipient, label):
        # Pro internal transfer initiation doesn't need a second step.
        pass

    def create_transfer(self, account, recipient, transfer):
        t = Transfer()
        t.currency = FrenchTransaction.Currency('''
            //span[@id="MM_VIREMENT_CONF_VIREMENT_MontantVir"]
            | //span[@id="MM_VIREMENT_CONF_VIREMENT_lblMontantSelect"]
        ''')(self.doc)
        t.amount = CleanDecimal(
            '''
                //span[@id="MM_VIREMENT_CONF_VIREMENT_MontantVir"]
                | //span[@id="MM_VIREMENT_CONF_VIREMENT_lblMontantSelect"]
            ''',
            replace_dots=True
        )(self.doc)
        t.account_iban = account.iban
        if recipient.category == 'Externe':
            all_text = Upper(CleanText('//span[@id="MM_VIREMENT_CONF_VIREMENT_lblCptCrediterResult"]'))(self.doc)
            for word in all_text.split():
                if is_iban_valid(word):
                    t.recipient_iban = word
                    break
            else:
                raise AssertionError('Unable to find IBAN (original was %s)' % recipient.iban)
        else:
            t.recipient_iban = recipient.iban
        t.recipient_iban = recipient.iban
        t.account_id = unicode(account.id)
        t.recipient_id = unicode(recipient.id)
        t.account_label = account.label
        t.recipient_label = recipient.label
        t._account = account
        t._recipient = recipient
        t.label = CleanText('''
            //span[@id="MM_VIREMENT_CONF_VIREMENT_Libelle"]
            | //span[@id="MM_VIREMENT_CONF_VIREMENT_lblMotifSelect"]
        ''')(self.doc)
        t.exec_date = Date(CleanText('//span[@id="MM_VIREMENT_CONF_VIREMENT_DateVir"]'), dayfirst=True)(self.doc)
        t.account_balance = account.balance
        return t


class ProTransferPage(TransferPage):
    RECIPIENT_XPATH = '//select[@id="MM_VIREMENT_SAISIE_VIREMENT_ddlCompteCrediterPro"]/option'

    def is_here(self):
        return CleanText('''
            //span[contains(text(), "Créer une liste de virements")] | //span[contains(text(), "Réalisez un virement")]
        ''')(self.doc)

    @method
    class iter_recipients(MyRecipients):
        pass

    def init_transfer(self, account, recipient, transfer):
        form = self.get_form(id='main')
        form['MM$VIREMENT$SAISIE_VIREMENT$ddlCompteDebiter'] = self.get_origin_account_value(account)
        form['MM$VIREMENT$SAISIE_VIREMENT$ddlCompteCrediterPro'] = self.get_recipient_value(recipient)
        form['MM$VIREMENT$SAISIE_VIREMENT$Libelle'] = transfer.label
        form['MM$VIREMENT$SAISIE_VIREMENT$m_oDEI_Montant$m_txtMontant'] = unicode(transfer.amount)
        form['__EVENTTARGET'] = 'MM$VIREMENT$m_WizardBar$m_lnkNext$m_lnkButton'
        if transfer.exec_date != datetime.today().date():
            form['MM$VIREMENT$SAISIE_VIREMENT$virement'] = 'rbDiffere'
            form['MM$VIREMENT$SAISIE_VIREMENT$m_DateDiffere$JJ'] = transfer.exec_date.strftime('%d')
            form['MM$VIREMENT$SAISIE_VIREMENT$m_DateDiffere$MM'] = transfer.exec_date.strftime('%m')
            form['MM$VIREMENT$SAISIE_VIREMENT$m_DateDiffere$AA'] = transfer.exec_date.strftime('%y')
        form.submit()

    def go_add_recipient(self):
        form = self.get_form(id='main')
        form['__EVENTTARGET'] = 'MM$VIREMENT$SAISIE_VIREMENT$ddlCompteCrediterPro'
        form['MM$VIREMENT$SAISIE_VIREMENT$ddlCompteCrediterPro'] = 'AC'
        form.submit()

    @method
    class iter_emitters(MyEmitters):

        class Item(MyEmitter):

            def obj_label(self):
                """
                Label looks like 'JEAN DUPONT - C.PROF. - 19XXX65 - Solde : 187,12 EUR'.
                We only keep the first half (name and account name).
                What's left is: 'JEAN DUPONT - C.PROF.'
                """
                raw_string = CleanText('.')(self)
                if '-' in raw_string:
                    return '-'.join(raw_string.split('-')[0:2])
                return raw_string

            def obj_balance(self):
                balance_data = CleanText('.')(self).split('Solde')[-1]
                return CleanDecimal().French().filter(balance_data)
