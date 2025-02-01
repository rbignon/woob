# Copyright(C) 2014      Bezleputh
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

from datetime import time

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import CleanHTML, Link
from woob.browser.filters.standard import CleanText, CombineDate, DateTime, Env, Filter, Regexp
from woob.browser.pages import HTMLPage

from .calendar import RazibusCalendarEvent


class EndTime(Filter):
    def filter(self, el):
        return time.max


class EventListPage(HTMLPage):
    @method
    class list_events(ListElement):
        item_xpath = '//div[@class="item"]'

        class item(ItemElement):
            klass = RazibusCalendarEvent

            def validate(self, obj):
                return self.is_valid_event(
                    obj, self.env["city"], self.env["categories"]
                ) and self.is_event_in_valid_period(obj.start_date, self.env["date_from"], self.env["date_to"])

            def is_valid_event(self, event, city, categories):
                if city and city != "" and city.upper() != event.city.upper():
                    return False
                if categories and len(categories) > 0 and event.category not in categories:
                    return False
                return True

            def is_event_in_valid_period(self, event_date, date_from, date_to):
                if event_date >= date_from:
                    if not date_to:
                        return True
                    else:
                        if event_date <= date_to:
                            return True
                return False

            obj_id = Regexp(Link('./p/strong/a[@itemprop="url"]'), "http://razibus.net/(.*).html")
            obj_summary = CleanText('./p/strong/a[@itemprop="url"]')
            obj_start_date = DateTime(CleanText('./p/span[@itemprop="startDate"]/@content'))
            obj_end_date = CombineDate(DateTime(CleanText('./p/span[@itemprop="startDate"]/@content')), EndTime("."))
            obj_location = CleanText('./p/span[@itemprop="location"]/@content')
            obj_city = CleanText('./p/span[@itemprop="location"]')


class EventPage(HTMLPage):
    @method
    class get_event(ItemElement):
        klass = RazibusCalendarEvent

        obj_id = Env("_id")
        obj_summary = CleanText('//h2[@itemprop="name"]')
        obj_start_date = DateTime(CleanText('//span[@itemprop="startDate"]/time/@datetime'))
        obj_end_date = CombineDate(DateTime(CleanText('//span[@itemprop="startDate"]/time/@datetime')), EndTime("."))
        obj_location = CleanText('//meta[@property="og:street-address"]/@content')
        obj_city = CleanText('//meta[@property="og:locality"]/@content')
        obj_url = CleanText('//meta[@property="og:url"]/@content')
        obj_description = CleanHTML('//div[@itemprop="description"]')
