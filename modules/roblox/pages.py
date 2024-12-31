# flake8: compatible

# Copyright(C) 2022 Thomas Touhey <thomas@touhey.fr>
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

import json
from decimal import Decimal

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.exceptions import ClientError
from woob.browser.filters.html import Attr
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, CleanText, Coalesce, Date, DateTime, Field, Format, Map
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, RawPage
from woob.capabilities.bank.base import Account, AccountOwnerType, Transaction
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.base import NotAvailable, empty
from woob.capabilities.captcha import FuncaptchaQuestion
from woob.capabilities.profile import Person
from woob.exceptions import BrowserIncorrectPassword

from .utils import InvalidSessionError


# ---
# Website pages.
# ---


class BasePage(HTMLPage):
    def get_csrf_token(self):
        return Attr(
            '//meta[@name="csrf-token"]',
            'data-token',
            default=None,
        )(self.doc)

    def get_user_id(self):
        return Attr('//meta[@name="user-data"]', 'data-userid')(self.doc)

    @method
    class get_profile(ItemElement):
        klass = Person

        obj_id = Attr('//meta[@name="user-data"]', 'data-userid')

    @method
    class get_account(ItemElement):
        klass = Account

        obj_id = Attr('//meta[@name="user-data"]', 'data-userid')
        obj_number = Attr('//meta[@name="user-data"]', 'data-name')
        obj_label = Attr('//meta[@name="user-data"]', 'data-displayname')
        obj_currency = 'X-RBX'  # TODO: Robux currency code
        obj_type = Account.TYPE_CHECKING
        obj_owner_type = AccountOwnerType.PRIVATE


class LoginPage(BasePage):
    pass


class AccountPage(LoggedPage, BasePage):
    pass


class InventoryPage(LoggedPage, JsonPage):
    @method
    class iter_investment(DictElement):
        item_xpath = 'Data/Items'

        def store(self, obj):
            # We do not want to store the object, so that they can be
            # aggregated in the browser.
            return obj

        # TODO: manage pagination here.

        class item(ItemElement):
            klass = Investment

            def condition(self):
                # Is only an investment if a resellable product.
                # Note that IsResellable is only set if the user is premium.
                return Dict('Product/IsLimited')(self)

            obj_id = Dict('Item/AssetId')
            obj_url = Dict('Item/AbsoluteUrl')
            obj_label = Dict('Item/Name')
            obj_quantity = Decimal(1)
            obj_valuation = CleanDecimal.SI(
                Dict('Product/PriceInRobux'),
                default=None,
            )
            obj_unitvalue = Field('valuation')


# ---
# Side APIs pages.
# ---


class ErrorAPIPage(JsonPage):
    def raise_if_error(self):
        """ All pages can return a section with errors. """

        try:
            error_data = self.doc['errors'][0]
        except (KeyError, IndexError):
            # No action required.

            return

        code = error_data['code']
        message = error_data['message']

        if code == 0:
            # Either CSRF token is no longer valid or session is no longer
            # valid, we need to try and login again.

            raise InvalidSessionError(message)
        elif code == 1:
            raise BrowserIncorrectPassword(message)
        elif code == 2:
            field_data = json.loads(error_data['fieldData'])
            self.browser.captcha_id = field_data['unifiedCaptchaId']

            # Captcha key is actually on another page.
            response = self.browser.captcha_metadata_api_page.open()
            public_key = response.get_funcaptcha_site_key(
                action='ACTION_TYPE_WEB_LOGIN',
            )

            raise FuncaptchaQuestion(
                website_key=public_key,
                website_url=self.browser.absurl('/'),
                sub_domain='roblox-api.arkoselabs.com',
            )
        elif code == 10:
            # The two step verification challenge code is invalid.
            raise BrowserIncorrectPassword(message)

        raise ClientError(f'Unmanaged error {code}: {message}')


class LoginAPIPage(JsonPage):
    def get_user_id(self):
        return Dict('user/id', default=None)(self.doc)

    def is_banned(self):
        return Dict('isBanned', default=False)(self.doc)

    def get_second_factor(self):
        media_type = Dict(
            'twoStepVerificationData/mediaType',
            default=None,
        )(self.doc)

        if empty(media_type):
            return

        ticket = Dict('twoStepVerificationData/ticket', default=None)(self.doc)
        return {'type': media_type, 'ticket': ticket}


class ValidateTwoFAAPIPage(RawPage):
    pass


class CaptchaMetadataAPIPage(JsonPage):
    def get_funcaptcha_site_key(self, action='ACTION_TYPE_WEB_LOGIN'):
        return Dict('funCaptchaPublicKeys/%s' % action, default=None)(self.doc)


class TwoFAValidateChallengeAPIPage(JsonPage):
    def get_verification_token(self):
        return Dict('verificationToken')(self.doc)


class EmailAPIPage(JsonPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        # NOTE: E-mail address can be null (at profile creation), and when
        #       available, is censored (e.g. j***@dupont.fr).
        obj_email = Coalesce(Dict('emailAddress'), default=None)


class PhoneAPIPage(JsonPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        # NOTE: Phone number can be null (at profile creation), and when
        #       available, is censored (e.g. +33 * ** ** 67 89).
        obj_phone = Coalesce(Dict('phone'), default=None)


class BirthdateAPIPage(JsonPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_birth_date = Date(Format(
            '%s-%s-%s',
            Dict('birthYear'),
            Dict('birthMonth'),
            Dict('birthDay'),
        ))


class GenderAPIPage(JsonPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_gender = Map(
            Dict('gender'),
            {1: 'female', 2: 'male'},
            default=NotAvailable,
        )


class CurrencyAPIPage(JsonPage):
    @method
    class get_account(ItemElement):
        klass = Account

        obj_balance = CleanDecimal.SI(
            Dict('robux'),
            default='0',
        )


class TransactionsAPIPage(JsonPage):
    @method
    class iter_history(DictElement):
        item_xpath = 'data'

        class item(ItemElement):
            klass = Transaction

            obj_id = Format('%d', Dict('id'))
            obj_date = obj_rdate = DateTime(Dict('created'))
            obj_amount = CleanDecimal.SI(Dict('currency/amount'))
            obj_type = Map(
                Field('_raw_type'),
                {
                    'Currency Purchase': Transaction.TYPE_TRANSFER,
                    'Purchase': Transaction.TYPE_TRANSFER,
                },
            )

            obj__raw_type = CleanText(Dict('transactionType'))

            def obj_label(self):
                transaction_type = Field('_raw_type')(self)
                if transaction_type == 'Purchase':
                    return CleanText(Dict('details/name'))(self)
                if transaction_type == 'Currency Purchase':
                    return transaction_type
                return NotAvailable
