# -*- coding: utf-8 -*-

# Copyright(C) 2020      Quentin Defenouillere
#
# This file is part of weboob.
#
# weboob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# weboob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with weboob. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

# Temporary imports before moving these classes in this file
from weboob.capabilities.bank import (
    PerVersion, PerProviderType, Per,
    Investment, Pocket, CapBankWealth,
)

from .base import BaseObject, StringField, DecimalField, EnumField, Enum
from .date import DateField

__all__ = [
    'PerVersion', 'PerProviderType', 'Per', 'Investment', 'Pocket',
    'MarketOrderType', 'MarketOrderDirection', 'MarketOrderPayment',
    'MarketOrder', 'CapBankWealth',
]


class MarketOrderType(Enum):
    UNKNOWN = 0
    MARKET = 1
    """Order executed at the current market price"""
    LIMIT = 2
    """Order executed with a maximum or minimum price limit"""
    TRIGGER = 3
    """Order executed when the price reaches a specific value"""


class MarketOrderDirection(Enum):
    UNKNOWN = 0
    BUY = 1
    SALE = 2


class MarketOrderPayment(Enum):
    UNKNOWN = 0
    CASH = 1
    DEFERRED = 2


class MarketOrder(BaseObject):
    """
    Market order
    """

    # Important: a Market Order always corresponds to one (and only one) investment
    label = StringField('Label of the market order')

    # MarketOrder values
    unitprice = DecimalField('Value of the stock at the moment of the market order')
    unitvalue = DecimalField('Current value of the stock associated with the market order')
    ordervalue = DecimalField('Limit value or trigger value, only relevant if the order type is LIMIT or TRIGGER')
    currency = StringField('Currency of the market order - not always the same as account currency')
    quantity = DecimalField('Quantity of stocks in the market order')
    amount = DecimalField('Total amount that has been bought or sold')

    # MarketOrder additional information
    order_type = EnumField('Type of market order', MarketOrderType, default=MarketOrderType.UNKNOWN)
    direction = EnumField('Direction of the market order (buy or sale)', MarketOrderDirection, default=MarketOrderDirection.UNKNOWN)
    payment_method = EnumField('Payment method of the market order', MarketOrderPayment, default=MarketOrderPayment.UNKNOWN)
    date = DateField('Creation date of the market order')
    validity_date = DateField('Validity date of the market order')
    execution_date = DateField('Execution date of the market order (only for market orders that are completed)')
    state = StringField('Current state of the market order (e.g. executed)')
    code = StringField('Identifier of the stock related to the order')
    stock_market = StringField('Stock market on which the order was executed')
