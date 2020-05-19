# -*- coding: utf-8 -*-

# Copyright(C) 2012 Romain Bignon
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

from __future__ import unicode_literals

import re

from weboob.browser.pages import LoggedPage, HTMLPage
from weboob.browser.elements import ItemElement, method, TableElement
from weboob.browser.filters.html import Link
from weboob.browser.filters.standard import (
    Date, CleanDecimal, CleanText, Base, Regexp, MapIn, Field,
)
from weboob.browser.filters.html import TableCell
from weboob.capabilities.bank import (
    Transfer, TransferFrequency, TransferStatus, TransferDateType,
)
from weboob.tools.capabilities.bank.iban import is_iban_valid

from .base_pages import fix_form


class CheckingPage(LoggedPage, HTMLPage):
    is_here = '//h2[text()="Synthèse de mes comptes"]'

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
