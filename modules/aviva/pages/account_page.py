# -*- coding: utf-8 -*-

# Copyright(C) 2012-2019  Budget Insight
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

from __future__ import unicode_literals

from woob.browser.pages import LoggedPage
from woob.browser.elements import ListElement, ItemElement, method
from woob.browser.filters.standard import CleanText, Field
from woob.browser.filters.html import AbsoluteLink
from woob.capabilities.bank import Account
from woob.capabilities.base import NotAvailable

from .detail_pages import BasePage


class AccountsPage(LoggedPage, BasePage):
    @method
    class iter_accounts(ListElement):
        item_xpath = '//div[contains(@class, "o-product-roundels")]/div[@data-policy]'

        class item(ItemElement):
            klass = Account

            obj_id = CleanText('./@data-policy')
            obj_number = Field('id')
            obj_label = CleanText('.//p[has-class("a-heading")]', default=NotAvailable)
            obj_url = AbsoluteLink('.//a[contains(text(), "Ma situation")]')

            def condition(self):
                # 'Prévoyance' div is for insurance contracts -- they are not bank accounts and thus are skipped
                ignored_accounts = (
                    'Prévoyance', 'Responsabilité civile', 'Complémentaire santé', 'Protection juridique',
                    'Habitation', 'Automobile',
                )
                return CleanText('../../div[has-class("o-product-tab-category")]', default=NotAvailable)(self) not in ignored_accounts
