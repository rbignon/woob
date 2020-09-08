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
import re

from weboob.capabilities.bank import Recipient
from weboob.browser.pages import LoggedPage, JsonPage
from weboob.browser.elements import ItemElement, DictElement, method
from weboob.browser.filters.standard import (
    CleanText, Currency, Format, CleanDecimal,
)
from weboob.browser.filters.json import Dict


class ListAuthentPage(LoggedPage, JsonPage):
    def get_handled_auth_methods(self):
        # Order in auth_methods is important, the first method we encouter
        # is the strong authentification we are going to do.
        auth_methods = ('password', 'otp', 'sms', 'notification')
        for auth_method in auth_methods:
            if Dict('content/%s' % auth_method)(self.doc):
                return auth_method


class InitAuthentPage(LoggedPage, JsonPage):
    def get_authent_id(self):
        return Dict('content')(self.doc)


class AuthentResultPage(LoggedPage, JsonPage):
    def get_status(self):
        return Dict('content/status', default=None)(self.doc)


class EmittersListPage(LoggedPage, JsonPage):
    def can_account_emit_transfer(self, account_id):
        code = Dict('erreur/code')(self.doc)
        if code == '90624':
            # Not the owner of the account:
            # Nous vous précisons que votre pouvoir ne vous permet pas
            # d'effectuer des virements de ce type au débit du compte sélectionné.
            return False
        elif code != '0':
            raise AssertionError('Unhandled code %s in transfer emitter selection' % code)

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


class CheckOtpPage(LoggedPage, JsonPage):
    def get_error(self):
       error = CleanText(Dict('erreur/libelle'))(self.doc)
       if error != 'OK':
           return error


class SendSmsPage(LoggedPage, JsonPage):
    pass


class ErrorJsonPage(JsonPage):
    def get_error(self):
        error = CleanText(Dict('erreur/libelle'))(self.doc)
        if error != 'OK':
            # The message is some partial html, the useful message
            # is at the beginning, before every html tag so we just retrieve the
            # first part of the message before any html tag.
            # If the message begins with html tags, the regex will skip those.
            m = re.search(r'^(?:<[^>]+>)*(.+?)(?=<[^>]+>)', error)
            if m:
                return m.group(1)
            return error


class AddRecipientPage(LoggedPage, ErrorJsonPage):
    pass


class TransferPage(LoggedPage, ErrorJsonPage):
    def get_transfer_amount(self):
        return CleanDecimal(Dict('content/montant/valeur'))(self.doc)

    def get_transfer_currency(self):
        return Currency(Dict('content/montant/monnaie/code'))(self.doc)
