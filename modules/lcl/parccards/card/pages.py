# Copyright(C) 2023 Powens
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

from woob.capabilities.bank import Account
from woob.browser.pages import LoggedPage, JsonPage
from woob.browser.elements import ItemElement, method, DictElement
from woob.browser.filters.standard import CleanText, Regexp, Format
from woob.browser.filters.json import Dict


class LoginPage(JsonPage):
    def get_token(self):
        return CleanText(Dict('token'))(self.doc)

    def get_logged_user(self):
        return CleanText(Dict('login'))(self.doc)

    def get_accounts_params(self):
        return Dict('possibleCardsToSee')(self.doc)

    @method
    class iter_accounts(DictElement):
        item_xpath = 'possibleCardsToSee'

        class item(ItemElement):
            klass = Account

            obj_label = Format(
                '%s %s - %s',
                CleanText(Dict('contract/personne/firstName')),
                CleanText(Dict('contract/personne/lastName')),
                CleanText(Dict('cardNumberEncrypted')),
            )
            obj_id = Format(
                '%s%s%s',
                CleanText(Dict('contract/personne/firstName')),
                CleanText(Dict('contract/personne/lastName')),
                Regexp(CleanText(Dict('cardNumberEncrypted')), r'(\d+)'),
            )
            obj_type = Account.TYPE_CARD
            obj_number = CleanText(Dict('cardNumberEncrypted'))
            obj_currency = 'EUR'
            obj__card_id = CleanText(Dict('cardId'))


class PeriodsPage(LoggedPage, JsonPage):
    def get_periods(self):
        return [period['periodeId'] for period in self.doc]
