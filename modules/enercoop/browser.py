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

from woob.browser import LoginBrowser, URL, need_login
from woob.capabilities.base import find_object
from woob.capabilities.gauge import Gauge, GaugeSensor

from .pages import (
    LoginPage, SubscriptionPage, StatsPage,
    BillsPage, ProfilePage,
    YearlyPage, MonthlyPage, DailyPage, HourlyPage,
)


class EnercoopBrowser(LoginBrowser):
    BASEURL = 'https://mon-espace.enercoop.fr'

    login = URL('/clients/sign_in', LoginPage)
    bills = URL('/factures', BillsPage)
    profile = URL('/mon-compte', ProfilePage)
    subscription = URL('/contrat', SubscriptionPage)

    pre_yearly = URL(r"/consommation$", StatsPage)
    yearly = URL(
        r"/consommation/conso_glo/(?P<y1>\d{4})-(?P<y2>\d{4})$", YearlyPage)
    monthly = URL(r"/consommation/conso_glo/(?P<year>\d{4})$", MonthlyPage)
    daily = URL(
        r"/consommation/conso_glo/(?P<year>\d{4})/(?P<month>\d{2})$",
        DailyPage
    )
    hourly = URL(
        r"/consommation/conso_glo/(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})$",
        HourlyPage
    )

    def do_login(self):
        self.location("/clients/sign_in")
        self.login.go(
            data={
                "ecppp_client[email]": self.username,
                "ecppp_client[password]": self.password,
                "authenticity_token": self.page.get_login_token(),
            }
        )

    def export_session(self):
        return {
            **super().export_session(),
            'url': self.bills.build(),
        }

    @need_login
    def get_profile(self):
        self.profile.go()
        yield self.page.get_profile()

    @need_login
    def iter_subscription(self):
        self.subscription.go()
        sub = self.page.get_subscription()
        self.profile.go()
        self.page.fill_sub(sub)
        yield sub

    @need_login
    def iter_documents(self, _):
        self.bills.go()
        for doc in self.page.iter_documents():
            yield doc

    @need_login
    def download_document(self, document):
        return self.open(document.url).content

    @need_login
    def iter_gauges(self):
        # TODO implement for multiple contracts
        # and for disabled contracts, consumption pages won't work
        self.subscription.go()
        pdl = self.page.get_pdl_number()
        return [Gauge.from_dict({
            "id": f"{pdl}",
            "name": "Consommation",
            "object": "Consommation",
        })]

    consumption_periods = {
        "yearly": "annuelle",
        "monthly": "mensuelle",
        "daily": "quotidienne",
        "hourly": "par demie-heure",
    }

    def iter_sensors(self, id, pattern=None):
        g = find_object(self.iter_gauges(), id=id)
        assert g

        return [
            GaugeSensor.from_dict({
                "id": f"{id}.c.{subid}",
                "name": f"Consommation électrique {name}",
                "unit": "kWh",
                "gaugeid": id,
            })
            for subid, name in self.consumption_periods.items()
        ]

    @need_login
    def iter_sensor_history(self, id):
        pdl, sensor_type, subid = id.split(".")
        assert sensor_type == "c"
        assert subid in ("yearly", "monthly", "daily", "hourly")

        # can't fetch stats of today, use yesterday (and the corresponding month/year)
        max_date = datetime.date.today() - datetime.timedelta(days=1)

        url_args = {}
        for unit in ("year", "month", "day"):
            if subid[0] != unit[0]:
                url_args[unit] = str(getattr(max_date, unit)).zfill(2)
            else:
                break

        if subid == "yearly":
            self.pre_yearly.go()
            self.location(self.page.yearly_url())
        else:
            getattr(self, subid).go(**url_args)

        for measure in self.page.iter_sensor_history():
            if measure.date.date() > max_date:
                continue
            yield measure
