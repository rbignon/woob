# -*- coding: utf-8 -*-

# Copyright(C) 2015      Matthieu Weber
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

import re, json

from dateutil.parser import parse as parse_date

from weboob.tools.compat import unicode
from weboob.browser.pages import JsonPage, HTMLPage
from weboob.capabilities.parcel import Parcel, Event, ParcelNotFound


class DHLExpressSearchPage(JsonPage):
    # Based on http://www.dhl.com/etc/designs/dhl/docroot/tracking/less/tracking.css
    STATUSES = {
        u'105': Parcel.STATUS_PLANNED,
        u'104': Parcel.STATUS_PLANNED,
        u'102': Parcel.STATUS_IN_TRANSIT,
        u'101': Parcel.STATUS_ARRIVED,
    }

    def get_info(self, _id):
        if u'errors' in self.doc:
            raise ParcelNotFound("No such ID: %s" % _id)
        elif u'results' in self.doc:
            result = self.doc[u'results'][0]
            p = Parcel(_id)
            p.history = [self.build_event(e) for e in result[u'checkpoints']]
            p.status = self.STATUSES.get(result[u'delivery'][u'code'], Parcel.STATUS_UNKNOWN)
            p.info = p.history[0].activity
            return p
        else:
            raise ParcelNotFound("Unexpected reply from server")

    def build_event(self, e):
        index = e[u'counter']
        event = Event(index)
        event.date = parse_date(e[u'date'] + " " + e.get(u'time', ''), dayfirst=True, fuzzy=True)
        event.location = e.get(u'location', '')
        event.activity = e[u'description']
        return event


class DeutschePostDHLSearchPage(HTMLPage):
    # Based on http://www.parcelok.com/delivery-status-dhl.html
    STATUSES = {
        # "": Parcel.STATUS_PLANNED,
        "Parcel center.": Parcel.STATUS_IN_TRANSIT,
        "Export parcel center.": Parcel.STATUS_IN_TRANSIT,
        "Parcel center of origin.": Parcel.STATUS_IN_TRANSIT,
        "Delivery successful.": Parcel.STATUS_ARRIVED,
    }

    def get_info(self, _id):
        try:
            return self.get_info_html(_id)
        except ParcelNotFound:
            return self.get_info_json(_id)

    def get_info_html(self, _id):
        result_id = self.doc.xpath('//dd[@class="mm_shipment-number"]')
        if not result_id:
            raise ParcelNotFound("No such ID: %s" % _id)
        result_id = result_id[0].text.split(" ")[-1]
        if result_id != _id:
            raise ParcelNotFound("ID mismatch: expecting %s, got %s" % (_id, result_id))

        p = Parcel(_id)
        events = self.doc.xpath('//div[@id="events-content-0"]//dl/div/*')
        p.history = list(reversed([self.build_html_event(i, dt, dd) for i,(dt,dd) in enumerate(zip(events[0::2], events[1::2]))]))
        status_msg = self.doc.xpath('//div[@class="mm_shipmentStatusText"]//dd[1]')[0].text.split(" ", 1)[1]
        if len(status_msg) > 0:
            p.status = self.STATUSES.get(status_msg, Parcel.STATUS_UNKNOWN)
        else:
            p.status = Parcel.STATUS_UNKNOWN
        p.info = p.history[-1].activity
        return p

    def get_info_json(self, _id):
        script = self.doc.xpath('//script[contains(text(), "__INITIAL_APP_STATE__")]')[0]
        data = json.loads(re.search('JSON.parse\("(.*)"\),', script.text.decode("unicode_escape")).group(1))
        result_id = data["sendungen"][0]["id"]
        if not result_id:
            raise ParcelNotFound("No such ID: %s" % _id)
        if result_id != _id:
            raise ParcelNotFound("ID mismatch: expecting %s, got %s" % (_id, result_id))

        p = Parcel(_id)
        events = data["sendungen"][0]["sendungsdetails"]["sendungsverlauf"]["events"]
        p.history = [self.build_json_event(i, e) for i,e in enumerate(events)]
        status_msg = data["sendungen"][0]["sendungsdetails"]["sendungsverlauf"]["kurzStatus"]
        if len(status_msg) > 0:
            p.status = self.STATUSES.get(status_msg, Parcel.STATUS_UNKNOWN)
        else:
            p.status = Parcel.STATUS_UNKNOWN

        p.info = p.history[-1].activity
        return p

    def build_html_event(self, index, dd, dt):
        event = Event(index)
        event.date = parse_date(dd.text[0:19], dayfirst=True, fuzzy=True)
        event.location = unicode(dd.text[20:])
        event.activity = unicode(dt.text)
        return event

    def build_json_event(self, index, ev):
        event = Event(index)
        event.date = parse_date(ev["datum"])
        event.location = unicode(ev.get("ort", ""))
        event.activity = unicode(ev["status"])
        return event
