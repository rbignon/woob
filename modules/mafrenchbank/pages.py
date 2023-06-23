# Copyright(C) 2022-2023 Powens
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

from woob.browser.elements import DictElement, ItemElement, ListElement, method
from woob.browser.filters.html import Attr
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    CleanDecimal, CleanText, Coalesce, Currency, Date, Map, Regexp,
)
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, PartialHTMLPage
from woob.capabilities.bank.base import Account, Transaction

TRANSACTION_TYPES = {
    'FRAIS GESTION COMPTE COURANT': Transaction.TYPE_BANK,
    'ACHAT PAR CARTE': Transaction.TYPE_CARD,
    'VIREMENT SEPA REÇU': Transaction.TYPE_TRANSFER,
}


class LoginPage(HTMLPage):
    def get_seed(self):
        return Regexp(
            CleanText('//script[contains(., "entrypoint.initialize(")]'),
            r"entrypoint\.initialize\('(.+?)',",
        )(self.doc)


class LoginAjaxPage(JsonPage):
    def is_sca_required(self):
        return Dict('showSca', default=False)(self.doc)

    def is_successful(self):
        return Dict('successful', default=False)(self.doc)

    def get_error_message(self):
        # Coalesce is used here since 'errorMessageTitle' can exist and
        # be null, and we want to provide '' to CleanText in this case.
        return CleanText(Coalesce(
            Dict('errorMessageTitle'),
            default='',
        ))(self.doc)


class HomePage(LoggedPage, HTMLPage):
    def get_nonce(self):
        return Attr(
            '//input[@name="__NonceValue"]',
            'value',
        )(self.doc)

    def get_verification_token(self):
        return Attr(
            '//input[@name="__RequestVerificationToken"]',
            'value',
        )(self.doc)


class CheckingAccountsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):
        item_xpath = 'properties/CurrentAccountsList'

        class item(ItemElement):
            klass = Account

            # 'cID' property is actually the account's IBAN in
            # compact form, i.e. unformatted (without spaces), and can
            # also be considered as the identifier for the account.
            #
            # Also the IBAN is used as an account number on the website,
            # and is shown both in the account list and on the page's
            # account, unlike on other websites where it might be
            # hidden behind pages or behind a second factor validation,
            # so we also set it as Account.number.
            obj_id = obj_iban = obj_number = CleanText(Dict('cID'))
            obj_label = CleanText(Dict('cProductName'))
            obj_type = Account.TYPE_CHECKING
            obj_balance = CleanDecimal.SI(Dict('mBalance'))
            obj_currency = Currency(Dict('cCurrency'))


class HistorySearchPage(LoggedPage, PartialHTMLPage):
    def get_product_id(self, account_id):
        # The account_id is the IBAN as 'FR761690800001XXXXXXXXXXXXX'.
        # We want to get the X-es here to search the equivalent checkbox
        # and extract the product identifier out of it.
        return Attr(
            '//div[@class="filter"][.//label/span[2]="%s"]//input'
            % account_id[14:],
            'value',
        )(self.doc)


class HistoryPage(LoggedPage, PartialHTMLPage):
    @method
    class iter_history(ListElement):
        item_xpath = '//li[contains(@class, "content-list-row")]'

        class item(ItemElement):
            klass = Transaction

            obj_date = Date(
                CleanText('.//div[@class="column date"]'),
                dayfirst=True,
            )
            obj_label = CleanText('.//div[@class="column description"]')
            obj_amount = CleanDecimal.French(
                './/div[@class="column amount"]',
            )

            # Required to get the transaction detail.
            obj__transaction_id = Attr('.', 'data-id')


class HistoryDetailPage(LoggedPage, PartialHTMLPage):
    @method
    class get_transaction(ItemElement):
        klass = Transaction

        obj_type = Map(
            CleanText('//th[text()="Type d\'opération"]/following-sibling::td'),
            TRANSACTION_TYPES,
            default=Transaction.TYPE_UNKNOWN,
        )
        obj_date = Date(
            CleanText(
                '//th[contains(., "Date de l\'opération")]'
                + '/following-sibling::td',
            ),
            dayfirst=True,
        )
        obj_rdate = Date(
            Coalesce(
                CleanText(
                    '//th[contains(., "Date de règlement")]'
                    + '/following-sibling::td',
                ),
                CleanText(
                    '//th[contains(., "Date d\'exécution")]'
                    + '/following-sibling::td',
                ),
            ),
            dayfirst=True,
        )
