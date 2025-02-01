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

from woob.browser import URL, LoginBrowser, need_login
from woob.tools.date import new_datetime

from .pages import CalendarPage, DocumentsPage, HomePage, LoginPage, SubscriptionPage, UsersPage


class LuccaBrowser(LoginBrowser):
    BASEURL = "https://www.ilucca.net"

    login = URL("/identity/login", LoginPage)
    home = URL("/home", HomePage)
    calendar = URL("/api/v3/leaves", CalendarPage)
    users = URL(
        r"/api/departments\?fields=id%2Cname%2Ctype%2Clevel%2Cusers.id%2Cusers.displayName%2Cusers.dtContractStart%2Cusers.dtContractEnd%2Cusers.manager.id%2Cusers.manager2.id%2Cusers.legalEntityID%2Cusers.calendar.id&date=since%2C1970-01-01",
        UsersPage,
    )
    subscription = URL(r"/api/v3/users/me", SubscriptionPage)
    payslips = URL(r"/api/v3/payslips", DocumentsPage)
    download_document = URL(r"/pagga/services/download/(?P<document_id>.+)")

    def __init__(self, subdomain, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.BASEURL = "https://%s.ilucca.net" % subdomain
        self.id_card_doc = None

    def do_login(self):
        self.login.go()
        self.page.do_login(self.username, self.password)

        if not self.home.is_here():
            self.page.check_error()
            raise Exception("error is not handled")

    @need_login
    def all_events(self, start, end):
        self.users.go()
        users = {u.id: u for u in self.page.iter_users()}

        last = None
        while True:
            if end:
                if end < start:
                    break
            else:
                if last and last + timedelta(days=300) < start:
                    self.logger.info("300 days without event, stopping")
                    break

            window_end = start + timedelta(days=14)

            params = {
                "date": "between,{},{}".format(start.strftime("%Y-%m-%d"), window_end.strftime("%Y-%m-%d")),
                "leavePeriod.ownerId": ",".join(str(u.id) for u in users.values()),
                "fields": "leavePeriod[id,ownerId,isConfirmed],isAm,date,color,isRemoteWork,leaveAccount[name,isRemoteWork]",
            }
            self.calendar.go(params=params)
            events = self.page.iter_events(start, users=users)
            for event in sorted(events, key=lambda ev: new_datetime(ev.start_date)):
                if end and event.start_date >= end:
                    continue
                yield event
                last = new_datetime(event.start_date)

            start = window_end + timedelta(days=1)

    @need_login
    def iter_subscriptions(self):
        params = {"fields": "id,employeeNumber,extendedData"}
        self.subscription.go(params=params)
        yield self.page.get_subscription()

        self.id_card_doc = self.page.get_id_card_document()

    @need_login
    def iter_documents(self, subscription):
        yield self.id_card_doc

        params = {
            "fields": "id,import[name,startDate,endDate]",
            "ownerId": subscription._owner_id,
            "orderBy": "import.endDate,desc,import.startDate,desc,import.creationDate,desc",
        }
        self.payslips.go(params=params)
        yield from self.page.iter_documents()
