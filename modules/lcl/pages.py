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
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.base import NotAvailable, empty
from woob.tools.capabilities.bank.investments import IsinType


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


PERSON_TYPES = {
    'PM': 'professionnels',
    'PP': 'particuliers',
}


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
        return Coalesce(
            Dict('userName', default=NotAvailable),
            Format(
                '%s %s',
                Dict('firstName', default=NotAvailable),
                Dict('lastName', default=NotAvailable)
            )
        )(self.doc)

    def get_website(self):
        return MapIn(Dict('personType'), PERSON_TYPES)(self.doc)

    def get_mfa_details(self):
        return (
            Dict('multiFactorAuth/type', default=NotAvailable)(self.doc),
            Dict('multiFactorAuth/device/name', default=NotAvailable)(self.doc),
        )


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
    pass


ACCOUNT_TYPES = {
    'Compte Courant': Account.TYPE_CHECKING,
    'Compte de dépôts': Account.TYPE_DEPOSIT,
    'Livret A': Account.TYPE_SAVINGS,
    'Livret Dév. Durable et Solidaire': Account.TYPE_SAVINGS,
    'Compte de nantissement': Account.TYPE_SAVINGS,
    'Livret de Dév. Durable et Solidaire': Account.TYPE_SAVINGS,
    "Plan d'Epargne en Actions": Account.TYPE_PEA,
    'Compte sur livret': Account.TYPE_SAVINGS,
    'OPTILION STRATEGIQUE': Account.TYPE_SAVINGS,
    'Compte épargne logement': Account.TYPE_SAVINGS,
    'Compte Commun': Account.TYPE_CHECKING,
}


ACCOUNT_OWNERSHIP = {
    'holder': AccountOwnership.OWNER,
    'coholder': AccountOwnership.CO_OWNER,
    'minor_representative': AccountOwnership.ATTORNEY,
}


class AccountOwnershipItemElement(ItemElement):
    obj__user_role = NotAvailable  # overwrite if available

    def get_ownership(self, owner):
        if re.search(r'(m|mr|me|mme|mlle|mle|ml)\.? (.*)\bou (m|mr|me|mme|mlle|mle|ml)\b(.*)', owner, re.IGNORECASE):
            return AccountOwnership.CO_OWNER
        elif 'user_name' in self.env and self.env['user_name'] in owner:
            return AccountOwnership.OWNER
        return NotAvailable

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


class AccountItem(AccountOwnershipItemElement):
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


class AccountsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):
        item_xpath = 'accounts'

        class item(AccountItem):
            pass


class TermAccountsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):
        item_xpath = 'term_accounts'

        class item(AccountItem):
            obj_number = obj_id = CleanText(Dict('contract_id'))
            obj_type = Account.TYPE_SAVINGS
            obj__internal_id = NotAvailable


class CardsPage(LoggedPage, JsonPage):
    @method
    class iter_cards(DictElement):
        item_xpath = None

        class item(AccountOwnershipItemElement):
            klass = Account

            # obj_id will be overwritten in `CardDetailsPage` to match cards already existing in the database
            # obj__id will be used in `iter_history`
            obj_id = obj__id = CleanText(Dict('id'))
            obj_label = Format('%s %s', CleanText(Dict('product/label')), CleanText(Dict('holder/name')))
            obj_balance = CleanDecimal.SI(Dict('amount/value'))
            obj_currency = Currency(Dict('amount/currency'))
            obj_type = Account.TYPE_CARD
            obj__transfer_id = None
            obj__market_link = None
            obj__internal_id = CleanText(Dict('internal_id'))
            obj__parent_internal_id = CleanText(Dict('account_internal_id'))


class CardSynthesisPage(LoggedPage, JsonPage):
    def is_card_available(self, card_internal_id):
        for account in self.doc.get('accounts', []):
            for card in account.get('bank_cards', []):
                if card['card_contract_id'] == card_internal_id:
                    return True
        return False


class CardDetailsPage(LoggedPage, JsonPage):
    @method
    class fill_card(ItemElement):
        klass = Account

        obj_number = CleanText(Dict('masked_pan'))

        def obj_id(self):
            last_numbers = Field('number')(self)[-3:]
            agency_code = CleanText(Dict('agency_code'))(self)
            account_number = CleanText(Dict('account_number'))(self)
            return agency_code + account_number[-7:] + '-' + last_numbers


class LifeInsurancesPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):
        item_xpath = 'life_insurance'

        class item(AccountItem):
            obj_number = obj_id = CleanText(Dict('contract_id'))
            obj_type = Account.TYPE_LIFE_INSURANCE
            obj__partner_label = CleanText(Dict('partner/label', default=''))
            obj__partner_code = CleanText(Dict('partner/code', default=''))


class LoansPage(LoggedPage, JsonPage):
    @method
    class iter_loans(DictElement):
        item_xpath = 'credits'

        class item(ItemElement):
            klass = Loan

            def condition(self):
                loan_type = CleanText(Dict('source_code'))(self.el)
                if loan_type == 'DAU':
                    # Overdraft account ( 'Autorisation de découvert' ) we skkip it.
                    self.logger.warning('Skip an Overdraft account')
                    return False
                self.logger.info('LCL: loan account found  %s', loan_type)
                return True

            obj_id = CleanText(Dict('id'))
            obj_label = CleanText(Dict('label'))
            obj_total_amount = CleanDecimal.SI(Dict('amount'))
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

            def obj__parent_id(self):
                branch = Field('_branch')(self)
                account = Field('_account')(self)
                key_letter = CleanText(Dict('key_letter'))(self)

                if len(account) == 4:
                    # pad to length 5
                    account = '0' + account

                return f'0{branch}0{account}{key_letter}'

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


TRANSACTION_TYPES = {
    'virement': Transaction.TYPE_TRANSFER,
    'vir sepa': Transaction.TYPE_TRANSFER,
    'prelvt': Transaction.TYPE_BANK,
    'prlv sepa': Transaction.TYPE_ORDER,
    'cb': Transaction.TYPE_CARD,
    'cotisation': Transaction.TYPE_BANK,
    'abon lcl': Transaction.TYPE_BANK,
}


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
    obj_type = MapIn(
        Lower(Field('label')),
        TRANSACTION_TYPES,
        Transaction.TYPE_UNKNOWN,
    )

    def obj__details_available(self):
        details_available = CleanText(Dict('are_details_available', default=''))(self)
        return details_available == 'True'

    def obj__is_accounted(self):
        is_accounted = CleanText(Dict('is_accounted', default=''))(self)
        return is_accounted == 'True'


class TransactionsPage(LoggedPage, JsonPage):
    def update_stop_condition(self):
        # if the number 100 is changed, we should do the same in the browser
        return len(self.doc['accountTransactions']) < 100

    @method
    class iter_transactions(DictElement):
        item_xpath = 'accountTransactions'

        class item(TransactionItem):
            # there's an id field but it is not unique
            pass


class SEPAMandatePage(LoggedPage, JsonPage):
    def update_stop_condition(self):
        # if the number 100 is changed, we should do the same in the browser
        return int(self.doc['total_size']) < 100

    @method
    class iter_transactions(DictElement):
        item_xpath = 'elements'

        class item(TransactionItem):
            obj_label = Format('%s %s', CleanText(Dict('creditor')), CleanText(Dict('mandate')))
            obj_amount = CleanDecimal.SI(Dict('amount'))
            obj_date = Date(
                Regexp(
                    CleanText(Dict('date')),
                    r'(.*)T',
                )
            )
            obj_type = Transaction.TYPE_TRANSFER


class CardTransactionsPage(LoggedPage, JsonPage):
    @method
    class iter_transactions(DictElement):
        item_xpath = None

        class item(TransactionItem):
            pass


class RoutagePage(LoggedPage, HTMLPage):
    def send_form(self):
        form = self.get_form()
        return form.submit()


class AVInvestmentsPage(LoggedPage, JsonPage):
    def update_life_insurance_account(self, life_insurance):
        life_insurance._owner = Format(
            '%s %s',
            Dict('situationAdministrativeEpargne/lppeoscp'),
            Dict('situationAdministrativeEpargne/lnpeoscp'),
        )(self.doc)
        life_insurance.label = '%s %s' % (
            Dict('situationAdministrativeEpargne/lcofc')(self.doc),
            life_insurance._owner,
        )
        life_insurance.valuation_diff = CleanDecimal(
            Dict('situationFinanciereEpargne/mtpmvcnt'),
            default=NotAvailable
        )(self.doc)
        return life_insurance

    @method
    class iter_investment(DictElement):
        item_xpath = 'listeSupports/support'

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(Dict('lcspt'))
            obj_valuation = CleanDecimal(Dict('mtvalspt'))
            obj_code = CleanText(Dict('cdsptisn'), default=NotAvailable)
            obj_unitvalue = CleanDecimal(Dict('mtliqpaaspt'), default=NotAvailable)
            obj_quantity = CleanDecimal(Dict('qtpaaspt'), default=NotAvailable)
            obj_diff = CleanDecimal(Dict('mtpmvspt'), default=NotAvailable)
            obj_vdate = Date(Dict('dvspt'), default=NotAvailable)
            obj_code_type = IsinType(Field('code'))

            def obj_portfolio_share(self):
                ptf = CleanDecimal(Dict('txrpaspt'), default=NotAvailable)(self)
                if empty(ptf):
                    return NotAvailable
                ptf /= 100
                return ptf


class AVHistoryPage(LoggedPage, JsonPage):
    @method
    class iter_history(DictElement):
        item_xpath = 'listeOperations'

        class item(ItemElement):
            klass = Transaction

            obj_label = CleanText(Dict('lcope'))
            obj_amount = CleanDecimal(Dict('mtope'))
            obj_type = Transaction.TYPE_BANK
            obj_investments = NotAvailable

            # The 'idope' key contains a string such as "70_ABC666ABC   2018-03-182018-03-16-20.55.27.960852"
            # 70= N° transaction, 6660666= N° account, 2018-03-18= date and 2018-03-16=rdate.
            # We thus use "70_ABC666ABC" for the transaction ID.

            obj_id = Regexp(CleanText(Dict('idope')), r'(\d+_[\dA-Z]+)')

            def obj__dates(self):
                raw = CleanText(Dict('idope'))(self)
                m = re.findall(r'\d{4}-\d{2}-\d{2}', raw)
                # We must verify that the two dates are correctly fetched
                assert len(m) == 2
                return m

            def obj_date(self):
                return Date().filter(Field('_dates')(self)[0])

            def obj_rdate(self):
                return Date().filter(Field('_dates')(self)[1])
