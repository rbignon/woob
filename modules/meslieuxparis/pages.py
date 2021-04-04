# -*- coding: utf-8 -*-

# Copyright(C) 2018      Vincent A
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from datetime import time, date

from dateutil import rrule
from woob.browser.elements import method, ItemElement, DictElement
from woob.browser.filters.standard import CleanText, Regexp
from woob.browser.filters.json import Dict
from woob.browser.pages import JsonPage
from woob.capabilities.base import NotAvailable
from woob.capabilities.contact import Place, OpeningRule, OpeningHours


def parsetime(s):
    return time(*map(int, s.split(':')))

def parsedate(s):
    return date(*map(int, s.split('-')))


class ListPage(JsonPage):
    def build_doc(self, content):
        content = content.strip()
        return super(ListPage, self).build_doc(content)

    @method
    class iter_contacts(DictElement):
        def find_elements(self):
            return self.el

        def condition(self):
            return 'ERR' not in self.el

        class item(ItemElement):
            klass = Place

            obj_id = Dict('idequipement')
            obj_name = Dict('name')
            obj_address = Dict('details/address')
            obj_postcode = Dict('details/zip_code')
            obj_city = Dict('details/city')
            obj_country = 'FR'
            obj_phone = Regexp(CleanText(Dict('details/phone'), replace=[(' ', '')]), r'^0(.*)$', r'+33\1', default=None)

            def obj_opening(self):
                if self.el['calendars'] == []:
                    # yes, sometimes it's a list
                    return NotAvailable

                if self.el['calendars'].get('everyday'):
                    rule = OpeningRule()
                    rule.dates = rrule.rrule(rrule.DAILY)
                    rule.times = [(time(0, 0), time(23, 59, 59))]
                    rule.is_open = True

                    res = OpeningHours()
                    res.rules = [rule]
                    return res

                rules = []
                for day, hours in self.el['calendars'].items():
                    rule = OpeningRule()
                    rule.is_open = True

                    day = parsedate(day)
                    rule.dates = rrule.rrule(rrule.DAILY, count=1, dtstart=day)
                    rule.times = [(parsetime(t[0]), parsetime(t[1])) for t in hours if t[0] != 'closed']
                    rule.is_open = True

                    if rule.times:
                        rules.append(rule)

                res = OpeningHours()
                res.rules = rules
                return res
