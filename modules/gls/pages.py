# Copyright(C) 2015      Matthieu Weber
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

from dateutil.parser import parse as parse_date

from woob.browser.pages import JsonPage
from woob.capabilities.parcel import Event, Parcel


STATUSES = {
    "PREADVICE": Parcel.STATUS_PLANNED,
    "INTRANSIT": Parcel.STATUS_IN_TRANSIT,
    "INWAREHOUSE": Parcel.STATUS_IN_TRANSIT,
    "INDELIVERY": Parcel.STATUS_IN_TRANSIT,
    "DELIVEREDPS": Parcel.STATUS_ARRIVED,
    "DELIVERED": Parcel.STATUS_ARRIVED,
}


class SearchPage(JsonPage):
    def get_info(self, _id):
        p = Parcel(_id)
        # TODO: temporary fix, history only available when we submit the recipient's postcode
        events = self.doc["tuStatus"][0].get("history", [])
        p.history = [self.build_event(i, tr) for i, tr in enumerate(events)]
        p.status = self.guess_status(self.doc["tuStatus"][0]["progressBar"]["statusInfo"])
        p.info = self.doc["tuStatus"][0]["progressBar"]["statusText"]
        return p

    def guess_status(self, code):
        return STATUSES.get(code, Parcel.STATUS_UNKNOWN)

    def build_event(self, index, data):
        event = Event(index)
        date = "{} {}".format(data["date"], data["time"])
        event.date = parse_date(date, dayfirst=False)
        event.location = ", ".join(
            [str(data["address"][field]) for field in ["city", "countryName"] if data["address"][field]]
        )
        event.activity = str(data["evtDscr"])
        return event
