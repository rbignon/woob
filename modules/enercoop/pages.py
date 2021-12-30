# -*- coding: utf-8 -*-

# Copyright(C) 2020      Vincent A
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

from __future__ import unicode_literals

import datetime
from decimal import Decimal
import json
import re

from dateutil.tz import gettz

from woob.browser.elements import (
    ItemElement, ListElement, method,
)
from woob.browser.pages import HTMLPage, NextPage, pagination
from woob.browser.filters.standard import (
    Date, CleanDecimal, CleanText, Format, Regexp, QueryValue,
)
from woob.browser.filters.html import (
    AbsoluteLink, Attr, FormValue,
)
from woob.capabilities.base import NotAvailable
from woob.capabilities.address import PostalAddress
from woob.capabilities.profile import Person
from woob.capabilities.bill import (
    Subscription, Bill,
)
from woob.capabilities.gauge import GaugeMeasure


SITE_TZ = gettz("Europe/Paris")


class LoggedMixin:
    @property
    def logged(self):
        return bool(self.doc.xpath('//a[@id="logout"]'))


class BillsPage(LoggedMixin, HTMLPage):
    @method
    class iter_other_subscriptions(ListElement):
        item_xpath = '//li[@id="contract-switch"]//a[@role="menuitem"][@href]'

        class item(ItemElement):
            klass = Subscription

            obj_url = AbsoluteLink('.')
            obj_id = QueryValue(obj_url, 'c')
            obj_number = Regexp(CleanText('.'), r'(CNT-\d+-\d+)')
            obj_label = Format(
                '%s %s',
                CleanText('./span', children=False),
                obj_number,
            )

    @method
    class iter_documents(ListElement):
        item_xpath = '//div[@id="invoices-container"]/ul/li'

        class item(ItemElement):
            klass = Bill

            obj_id = Attr('.', 'data-invoice-id')

            obj_total_price = CleanDecimal.French('.//div[has-class("amount")]')
            obj_currency = 'EUR'

            obj_date = Date(CleanText('.//div[has-class("dueDate")]'), dayfirst=True)
            obj_label = Format("%s %s", obj_id, obj_date)

            obj_format = 'pdf'

            def obj_url(self):
                url = AbsoluteLink('.//a[@target="_blank"]')(self)
                if '//download' in url:
                    return NotAvailable
                return url

            def obj_has_file(self):
                return bool(self.obj_url())


class ProfilePage(LoggedMixin, HTMLPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_name = FormValue('//input[@name="name"]')
        obj_email = FormValue('//input[@name="email"]')
        obj_phone = Format(
            '%s%s',
            Regexp(
                CleanText(FormValue('//select[@id="phone_number_indic"]')),
                r'\+\d+'
            ),
            FormValue('//input[@id="phone_number"]')
        )
        obj_country = 'France'

        class obj_postal_address(ItemElement):
            klass = PostalAddress

            # there can be a lot of whitespace in city name
            obj_city = CleanText(FormValue('//select[@id="cities"]'))

            obj_street = Format(
                '%s %s',
                FormValue('//input[@name="num"]'),
                FormValue('//input[@name="street"]')
            )
            obj_postal_code = FormValue('//input[@name="zip_code"]')
            obj_country = 'France'

    def fill_sub(self, sub):
        sub._profile = self.get_profile()
        sub.subscriber = sub._profile.name

    def get_pdl_number(self):
        text = CleanText("""//div[contains(text(),"Numéro de PDL")]/../..""")(self.doc)
        return re.search(r"(\d+)", text)[1]


class StatsPage(LoggedMixin, HTMLPage):
    ABSOLUTE_LINKS = True

    @pagination
    def iter_sensor_history(self):
        yield from self._history_on_page()

        prev_links = self.doc.xpath("//a[has-class('previous')]/@href")
        if prev_links:
            raise NextPage(prev_links[0])

    def _history_on_page(self):
        script_l = self.doc.xpath("//script[@id='enedis-api-response']")
        if not script_l:
            return

        xvalues = json.loads(script_l[0].attrib["data-x-axis-values"])
        yvalues = json.loads(script_l[0].attrib["data-y-axis-values"])

        xvalues, yvalues = self._tweak_values(xvalues, yvalues)
        if all(yv == 0 for yv in yvalues):
            self.logger.warning("all values are 0 for %r... ignoring whole page", self.params)
            return

        date_builder = {"tzinfo": SITE_TZ}

        units = ["year", "month", "day"]
        for unit in units:
            date_builder[unit] = int(self.params.get(unit, 1))

        for x, y in reversed(list(zip(xvalues, yvalues))):
            date_builder.update(x)
            measure_date = datetime.datetime(**date_builder)
            yield GaugeMeasure.from_dict({
                "date": measure_date,
                "level": Decimal(str(y)),
            })

    def _tweak_values(self, xvalues, yvalues):
        xvalues = [{self.vary_unit: v} for v in xvalues]
        return xvalues, yvalues


class YearlyPage(StatsPage):
    vary_unit = "year"


class MonthlyPage(StatsPage):
    vary_unit = "month"

    def _tweak_values(self, xvalues, yvalues):
        assert len(xvalues) == 12
        assert xvalues[0] == "Janvier"

        xvalues = [{self.vary_unit: v} for v in range(1, 13)]
        return xvalues, yvalues


class DailyPage(StatsPage):
    vary_unit = "day"


class HourlyPage(StatsPage):
    vary_unit = "hour"

    def _tweak_values(self, xvalues, yvalues):
        if not xvalues:
            return [], []

        assert xvalues[0] == "00:00"

        xnew = []
        for h in range(24):
            for m in (0, 30):
                xnew.append({"hour": h, "minute": m})

        ynew = yvalues

        assert len(xnew) == len(ynew)

        return xnew, ynew
