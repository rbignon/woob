# Copyright(C) 2022      Budget Insight
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
import codecs

from woob.browser.pages import LoggedPage, JsonPage, HTMLPage, RawPage
from woob.browser.elements import method, ItemElement, DictElement
from woob.browser.filters.standard import (
    CleanText, Coalesce, Eval, Field, Regexp, Date, CleanDecimal, Map, Currency, MapIn, Lower, Format,
)
from woob.browser.filters.json import Dict
from woob.capabilities.bank import Loan, Account, AccountOwnership
from woob.capabilities.bank.base import Transaction
from woob.capabilities.base import NotAvailable, empty


class KeypadPage(JsonPage):
    def encode_password(self, password):
        decode_hex = codecs.getdecoder("hex_codec")

        keypad = self.get_keypad()
        # keypad = '63735393338303134323835323533663633313839393732673832303364353165313268343535356532643666366433346135343460333132616136653533373632643563643331313265393232693839303933643234656433333467343563323636603162353661353'

        encoded_keys, seed = keypad[:20], keypad[20:]
        # encoded_keys = '63735393338303134323'
        # seed = '835323533663633313839393732673832303364353165313268343535356532643666366433346135343460333132616136653533373632643563643331313265393232693839303933643234656433333467343563323636603162353661353'

        encoded_keys = encoded_keys[::-1]
        # encoded_keys = '32343130383339353736'

        keys = decode_hex(encoded_keys)[0].decode('utf-8')
        # keys = '2410839576' => virtual keyboard keys in order= 2 4 1 0 8 3 9 5 7 6

        mapped_password = self.map_password(keys, password)
        # we find the position of each password number in the keys
        # example password = '12345' => mapped_password = 2 0 5 1 7 = '20517'

        encoded_password = ''.join(mapped_password).encode("utf-8").hex()
        # we encode each number of the mapped password and concat in a string
        # 2 0 5 1 7 => 32 30 35 31 37 = '3230353137'

        encoded_password = encoded_password[::-1]
        # encoded_password = 7313530323

        # return encoded password + seed
        # example: '3230353137' + '835323533663633313839393732673832303364353165313268343535356532643666366433346135343460333132616136653533373632643563643331313265393232693839303933643234656433333467343563323636603162353661353'
        return encoded_password + seed

    def map_password(self, keys, password):
        return [str(keys.index(char)) for char in password]

    def get_keypad(self):
        return Dict('keypad')(self.doc)


class LoginPage(JsonPage):
    def get_error(self):
        return Dict('code')(self.doc), Dict('message')(self.doc)

    def get_authentication_data(self):
        return (
            Dict('accessToken')(self.doc),
            Dict('refreshToken')(self.doc),
            Dict('expiresAt')(self.doc),
            Dict('encryptedExpiresAt')(self.doc),
            Dict('userIdForBascule')(self.doc),
        )

    def get_user_id(self):
        return Dict('userId')(self.doc)

    def get_contract_id(self):
        return Dict('contracts/0/id')(self.doc)

    def get_user_name(self):
        return f"{Dict('firstName')(self.doc)} {Dict('lastName')(self.doc)}"


class RedirectionPage(HTMLPage):
    def go_pre_home(self):
        form = self.get_form(id='form')
        form.submit()


class PreHomePage(HTMLPage):
    def go_home(self):
        form = self.get_form(id='form')
        form.submit()


class HomePage(LoggedPage, RawPage):
    pass


class RedirectMonEspaceHome(LoggedPage, RawPage):
    pass


class MonEspaceHome(LoggedPage, RawPage):
    pass


class AggregationPage(LoggedPage, JsonPage):
    def is_enrolled(self):
        return Dict('is_enrolled')(self.doc)


ACCOUNT_TYPES = {
    'Compte de dépôts': Account.TYPE_CHECKING,
    'Livret A': Account.TYPE_SAVINGS,
    'Compte de nantissement': Account.TYPE_SAVINGS,
    'Livret de Dév. Durable et Solidaire': Account.TYPE_SAVINGS,
    "Plan d'Epargne en Actions": Account.TYPE_PEA,
    'Compte sur livret': Account.TYPE_SAVINGS,
}


ACCOUNT_OWNERSHIP = {
    'holder': AccountOwnership.OWNER,
    'coholder': AccountOwnership.CO_OWNER,
    'minor_representative': AccountOwnership.ATTORNEY,
}


class OwnedItemElement(ItemElement):
    def get_ownership(self, owner):
        if re.search(r'(m|mr|me|mme|mlle|mle|ml)\.? (.*)\bou (m|mr|me|mme|mlle|mle|ml)\b(.*)', owner, re.IGNORECASE):
            return AccountOwnership.CO_OWNER
        elif self.env['user_name'] in owner:
            return AccountOwnership.OWNER
        return NotAvailable


class AccountItem(OwnedItemElement):
    klass = Account

    obj_number = obj_id = CleanText(Dict('external_id'), replace=[(' ', '')])
    obj_label = CleanText(Dict('label'))
    obj_balance = CleanDecimal.SI(Dict('amount/value'))
    obj_currency = Currency(Dict('amount/currency'))
    obj_iban = CleanText(Dict('iban', default=''), default=NotAvailable)
    obj_type = Map(Field('label'), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)
    obj__user_role = Map(Lower(Dict('user_role', default='')), ACCOUNT_OWNERSHIP, NotAvailable)
    obj__internal_id = CleanText(Dict('internal_id'))
    obj__transfer_id = None
    obj__market_link = None

    def obj_ownership(self):
        user_role = Field('_user_role')(self)
        if not empty(user_role):
            return user_role

        return Eval(
            self.get_ownership,
            Coalesce(
                CleanText(Dict('holder_name', default='')),
                CleanText(Dict('holder_label', default='')),
                Format(
                    '%s %s',
                    CleanText(Dict('holder/first_name', default='')),
                    CleanText(Dict('holder/last_name', default='')),
                ),
            )
        )(self)


class AccountsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):
        item_xpath = 'accounts'

        class item(AccountItem):
            pass


class CardsPage(LoggedPage, JsonPage):
    @method
    class iter_cards(DictElement):
        item_xpath = None

        class item(OwnedItemElement):
            klass = Account

            obj_id = CleanText(Dict('id'))
            obj_label = CleanText(Dict('product/label'))
            obj_balance = CleanDecimal.SI(Dict('amount/value'))
            obj_currency = Currency(Dict('amount/currency'))
            obj_type = Account.TYPE_CARD
            obj__transfer_id = None
            obj__market_link = None
            obj__parent_internal_id = CleanText(Dict('account_internal_id'))

            def obj_ownership(self):
                return Eval(
                    self.get_ownership,
                    Coalesce(
                        CleanText(Dict('holder_name', default='')),
                        CleanText(Dict('holder_label', default='')),
                        Format(
                            '%s %s',
                            CleanText(Dict('holder/first_name', default='')),
                            CleanText(Dict('holder/last_name', default='')),
                        ),
                    )
                )(self)


class LifeInsurancesPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):
        item_xpath = 'life_insurance'

        class item(AccountItem):
            obj_number = obj_id = CleanText(Dict('contract_id'))
            obj_type = Account.TYPE_LIFE_INSURANCE


class LoansPage(LoggedPage, JsonPage):
    @method
    class iter_loans(DictElement):
        item_xpath = 'credits'

        class item(ItemElement):
            klass = Loan

            obj_id = CleanText(Dict('id'))
            obj_label = CleanText(Dict('label'))
            obj_amount = CleanDecimal.SI(Dict('amount'))
            obj_currency = Currency(Dict('currency'))
            obj_type = Account.TYPE_LOAN

            obj__source_code = CleanText(Dict('source_code'))
            obj__product_code = CleanText(Dict('product_code'))
            obj__branch = CleanText(Dict('branch'))
            obj__account = CleanText(Dict('account'))
            obj__legacy_id = Format(
                '0%s0%s%s%s',
                Field('_branch'),
                Field('_account'),
                CleanText(Dict('key_letter')),
                CleanText(Field('label'), replace=[(' ', '')]),
            )
            obj__transfer_id = None
            obj__market_link = None
            obj__parent_id = Format(
                '0%s0%s%s',
                Field('_branch'),
                Field('_account'),
                CleanText(Dict('key_letter')),
            )


class LoanDetailsPage(LoggedPage, JsonPage):
    @method
    class fill_loan(ItemElement):
        klass = Loan

        obj_balance = CleanDecimal.SI(Dict('sum_owed'), sign='-')
        obj_available_amount = CleanDecimal.SI(Dict('available_amount'))
        obj_rate = CleanDecimal.SI(Dict('eir'))
        obj_maturity_date = Date(CleanText(Dict('final_due_date', default='')), default=NotAvailable)
        obj_last_payment_amount = CleanDecimal.SI(Dict('last_due_date_amount'))
        obj_last_payment_date = Date(CleanText(Dict('last_due_date', default='')), default=NotAvailable)
        obj_next_payment_amount = CleanDecimal.SI(Dict('next_due_date_amount'))
        obj_next_payment_date = Date(CleanText(Dict('next_due_date', default='')), default=NotAvailable)


class TransactionItem(ItemElement):
    klass = Transaction

    obj_label = CleanText(Dict('label'))
    obj_amount = CleanDecimal.SI(Dict('amount/value'))
    obj_date = Date(
        Regexp(
            CleanText(Dict('booking_date_time')),
            r'(.*)T',
        )
    )

    def obj__details_available(self):
        details_available = CleanText(Dict('are_details_available', default=''))(self)
        return details_available == 'True'

    def obj__is_accounted(self):
        is_accounted = CleanText(Dict('is_accounted', default=''))(self)
        return is_accounted == 'True'


class TransactionsPage(LoggedPage, JsonPage):
    @method
    class iter_transactions(DictElement):
        item_xpath = 'accountTransactions'

        class item(TransactionItem):
            pass


class CardTransactionsPage(LoggedPage, JsonPage):
    @method
    class iter_transactions(DictElement):
        item_xpath = None

        class item(TransactionItem):
            obj_id = CleanText(Dict('id'))


TRANSACTION_TYPES = {
    'virement': Transaction.TYPE_TRANSFER,
    'prelvt': Transaction.TYPE_BANK,
}


class TransactionDetailsPage(LoggedPage, JsonPage):
    @method
    class fill_transaction(ItemElement):
        obj_type = MapIn(
            Lower(CleanText(Dict('nature', default=''))),
            TRANSACTION_TYPES,
            Transaction.TYPE_UNKNOWN,
        )
