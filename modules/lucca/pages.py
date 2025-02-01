# Copyright(C) 2018      Vincent A
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

from datetime import timedelta

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import BrowserURL, CleanText, Date, DateTime, Field, Format
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage
from woob.capabilities.bill import Document, DocumentTypes, Subscription
from woob.capabilities.calendar import STATUS, BaseCalendarEvent
from woob.exceptions import BrowserIncorrectPassword
from woob.tools.date import new_date, parse_date


class LoginPage(HTMLPage):
    def do_login(self, username, password):
        form = self.get_form(xpath='//form[@action="/identity/login"]')
        form["UserName"] = username
        form["Password"] = password
        form.submit()

    def check_error(self):
        msg = CleanText('//div[has-class("validation-summary-errors")]')(self.doc)
        if msg:
            raise BrowserIncorrectPassword(msg)


class HomePage(LoggedPage, HTMLPage):
    pass


class User:
    id = None
    name = None
    start = None
    end = None


class UsersPage(LoggedPage, JsonPage):
    def iter_users(self):
        for dpt in self.doc["data"]:
            for d in dpt["users"]:
                u = User()
                u.id = d["id"]
                u.name = d["displayName"]

                v = d["dtContractStart"]
                if v:
                    u.start = parse_date(v)
                v = d["dtContractEnd"]
                if v:
                    u.end = parse_date(v)

                yield u


class CalendarPage(LoggedPage, JsonPage):
    def iter_events(self, start_date, users):
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

        # key: (userId, date)
        events = {}

        for d in self.doc["data"]["items"]:
            if not d["leavePeriod"]["isConfirmed"]:
                # not validated by manager
                continue

            if d["isRemoteWork"]:
                continue

            user_id = d["leavePeriod"]["ownerId"]
            user = users[user_id]

            ev = BaseCalendarEvent()
            ev.timezone = "Europe/Paris"
            ev.summary = user.name
            ev.status = STATUS.CONFIRMED

            ev.start_date = DateTime().filter(d["date"])
            if not d["isAM"]:
                ev.start_date = ev.start_date + timedelta(hours=12)
                ev.end_date = ev.start_date + timedelta(hours=12)
            else:
                ev.end_date = ev.start_date + timedelta(hours=12)

            if user.end and new_date(user.end) < new_date(ev.start_date):
                continue

            event_key = user_id, ev.start_date.date()
            if event_key in events:
                ev.start_date = ev.start_date.date()
                ev.end_date = ev.start_date + timedelta(days=1)

            events[event_key] = ev

        return events.values()


class SubscriptionPage(LoggedPage, JsonPage):
    @method
    class get_subscription(ItemElement):
        klass = Subscription

        obj_id = CleanText(Dict("data/employeeNumber"))
        obj_label = Field("id")
        obj_subscriber = CleanText(Dict("header/principal"))
        obj__owner_id = Dict("data/id")

    def get_id_card_document(self):
        iddoc = Document()
        els = self.doc["data"]["extendedData"]["e_iddocuments"]
        for el in els:
            value = el["value"]["e_iddocuments_document"]["value"]
            # CNI: Carte national d'identité
            if "CNI" in value["name"]:
                iddoc.id = value["id"]
                iddoc.label, iddoc.format = value["name"].rsplit(".", 1)
                iddoc.url = value["href"]
                return iddoc


class DocumentsPage(LoggedPage, JsonPage):
    @method
    class iter_documents(DictElement):
        item_xpath = "data/items"

        class item(ItemElement):
            klass = Document

            obj_id = CleanText(Dict("id"))
            obj_label = Format("Fiche de paie %s", CleanText(Dict("import/name")))
            obj_date = Date(CleanText(Dict("import/endDate")))
            obj_url = BrowserURL("download_document", document_id=Field("id"))
            obj_type = DocumentTypes.PAYSLIP
            obj_format = "pdf"
