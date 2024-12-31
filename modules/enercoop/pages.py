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

import datetime
import json
import re
from decimal import Decimal

from dateutil.tz import gettz

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import AbsoluteLink, FormValue
from woob.browser.filters.standard import CleanDecimal, CleanText, Date, Format, Regexp
from woob.browser.pages import HTMLPage, NextPage, pagination
from woob.capabilities.address import PostalAddress
from woob.capabilities.bill import Bill, DocumentTypes, Subscription
from woob.capabilities.gauge import GaugeMeasure
from woob.capabilities.profile import Person


SITE_TZ = gettz("Europe/Paris")


class LoginPage(HTMLPage):
    def get_login_token(self):
        form = self.get_form(id="new_ecppp_client")
        return form.get("authenticity_token")


class LoggedMixin:
    @property
    def logged(self):
        return bool(self.doc.xpath('//a[@href="/clients/sign_out"]'))


class BillsPage(LoggedMixin, HTMLPage):
    @pagination
    @method
    class iter_documents(ListElement):
        item_xpath = '//div[has-class("container-fluid")]/div[@id="facture-table"]/div[has-class("js-accordion-container")]'
        next_page = AbsoluteLink(
            '//a[@title="Année précédente"]', default=None)

        class item(ItemElement):
            klass = Bill

            obj_id = CleanText(
                './div[has-class("table-line")]/div/div[2]', children=False)

            obj_total_price = CleanDecimal.French(
                Regexp(
                    CleanText('./div[has-class("table-line")]/div/div[3]'),
                    r"(\d+,\d+)",
                    nth=0,
                )
            )

            obj_currency = 'EUR'

            obj_date = Date(
                Regexp(
                    CleanText('./div[has-class("table-line")]/div/div[4]'),
                    r"(\d+/\d+/\d+)",
                    nth=0,
                ),
                dayfirst=True,
            )

            obj_label = Format("%s %s", obj_id, obj_date)

            obj_type = DocumentTypes.BILL

            obj_format = 'pdf'

            def obj_url(self):
                url = AbsoluteLink(".//a")(self)
                return url

            def obj_has_file(self):
                return bool(self.obj_url())


class SubscriptionPage(LoggedMixin, HTMLPage):
    @method
    class get_subscription(ItemElement):
        klass = Subscription

        root_xpath = '//div[has-class("container-fluid")]/div/div[2]'
        obj_id = CleanText(root_xpath + '/div[1]/div[has-class("value")]')
        obj_label = CleanText(root_xpath + "/span", children=False)

    def get_pdl_number(self):
        text = CleanText(
            '//div[has-class("container-fluid")]/div/div[2]/div[2]/div[has-class("value")]'
        )(self.doc)
        return re.search(r"(\d+)", text)[1]


class ProfilePage(LoggedMixin, HTMLPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_name = FormValue('//input[@name="name"]')
        obj_email = FormValue('//input[@name="email"]')
        obj_phone = FormValue('//input[@name="fixed_phone1"]')
        obj_country = 'France'

        class obj_postal_address(ItemElement):
            klass = PostalAddress

            obj_city = CleanText(
                FormValue('//select[@id="invoicing_address_city"]'))
            obj_street = Format(
                "%s %s",
                FormValue('//input[@name="invoicing_address_street_number"]'),
                FormValue('//input[@name="invoicing_address_street_name"]'),
            )
            obj_postal_code = FormValue(
                '//input[@name="invoicing_address_zipcode"]')
            obj_country = 'France'
            obj_country_code = 'FR'

    def fill_sub(self, sub):
        sub._profile = self.get_profile()
        sub.subscriber = sub._profile.name


class StatsPage(LoggedMixin, HTMLPage):
    @pagination
    def iter_sensor_history(self, sensor):
        yield from self._history_on_page(sensor)

        prev_links = self.doc.xpath("//a[text()='Précédent']/@href")
        if prev_links:
            raise NextPage(prev_links[0])

    def _history_on_page(self, sensor):
        canvas_l = self.doc.xpath("//canvas[@id='" + sensor + "']")
        if not canvas_l:
            return

        xvalues = json.loads(canvas_l[0].attrib["data-x-axis-values"])
        yvalues = json.loads(canvas_l[0].attrib["data-y-axis-values"])

        xvalues, yvalues = self._tweak_values(xvalues, yvalues)
        if all(yv == 0 for yv in yvalues):
            self.logger.warning(
                "all values are 0 for %r... ignoring whole page", self.params
            )
            return

        date_builder = {"tzinfo": SITE_TZ}

        units = ["year", "month", "day"]
        for unit in units:
            date_builder[unit] = int(self.params.get(unit, 1))

        if 'mixed_cadrans' in yvalues:
            yvalues = yvalues['mixed_cadrans']
        elif 'puissance_max' in yvalues:
            yvalues = yvalues['puissance_max']
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

    def yearly_url(self):
        return self.doc.xpath("//a[text()='Consommation annuelle']/@href")[0]


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

        if xvalues[0] == "00:15":
            # xvalues[] is ['00:15', '00:30', '00:45', '01:00', ..., '00:00']
            # move last element into first to have:
            # ['00:00', '00:15', '00:30', '00:45', '01:00', ..., '23:45']
            xvalues = xvalues[-1:] + xvalues[:-1]

        assert xvalues[0] == "00:00"

        xnew = []
        for v in xvalues:
            (h, m) = map(int, v.split(':'))
            xnew.append({"hour": h, "minute": m})

        ynew = yvalues['mixed_cadrans']

        assert len(xnew) == len(ynew)

        return xnew, ynew
