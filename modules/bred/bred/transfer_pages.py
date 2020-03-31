# -*- coding: utf-8 -*-

# Copyright(C) 2020 Guillaume Risbourg
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

from __future__ import unicode_literals

from datetime import date

from weboob.capabilities.bank import Recipient
from weboob.browser.pages import LoggedPage, JsonPage
from weboob.browser.elements import ItemElement, DictElement, method
from weboob.browser.filters.standard import CleanText, Currency, Format
from weboob.browser.filters.json import Dict


class EmittersListPage(LoggedPage, JsonPage):
    def can_account_emit_transfer(self, account_id):
        for obj in Dict('content')(self.doc):

            for account in Dict('postes')(obj):
                _id = '%s.%s' % (
                    Dict('numero')(obj),
                    Dict('codeNature')(account),
                )
                if _id == account_id:
                    return True
        return False


class RecipientListPage(LoggedPage, JsonPage):
    @method
    class iter_external_recipients(DictElement):
        item_xpath = 'content/listeComptesCExternes'

        class item(ItemElement):
            klass = Recipient

            obj_id = CleanText(Dict('id'))
            obj_iban = CleanText(Dict('iban'))
            obj_bank_name = CleanText(Dict('nomBanque'))
            obj_currency = Currency(Dict('monnaie/code'))
            obj_enabled_at = date.today()
            obj_label = CleanText(Dict('libelle'))
            obj_category = 'Externe'

    @method
    class iter_internal_recipients(DictElement):
        def find_elements(self):
            for obj in Dict('content/listeComptesCInternes')(self):
                number = Dict('numero')(obj)
                for account in Dict('postes')(obj):
                    account['number'] = number
                    yield account

        class item(ItemElement):
            klass = Recipient

            obj_id = Format('%s.%s', Dict('number'), Dict('codeNature'))
            obj_label = CleanText(Dict('libelle'))
            obj_enabled_at = date.today()
            obj_currency = Currency(Dict('monnaie/code'))
            obj_bank_name = 'BRED'
            obj_category = 'Interne'
