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

from woob.browser import URL, LoginBrowser, need_login
from woob.capabilities.base import find_object
from woob.capabilities.gauge import Gauge, GaugeSensor

from .pages import (
    BillsPage, DailyPage, HourlyPage, LoginPage, MonthlyPage, ProfilePage, StatsPage, SubscriptionPage, YearlyPage,
)


class EnercoopBrowser(LoginBrowser):
    BASEURL = 'https://mon-espace.enercoop.fr'

    login = URL('/clients/sign_in', LoginPage)
    bills = URL('/factures', BillsPage)
    profile = URL('/mon-compte', ProfilePage)
    subscription = URL('/contrat', SubscriptionPage)

    # Consumption sensor URLs
    pre_yearly = URL(r"/consommation$", StatsPage)
    c_yearly = URL(
        r"/consommation/conso_glo/(?P<y1>\d{4})-(?P<y2>\d{4})$",
        YearlyPage
    )
    c_monthly = URL(
        r"/consommation/conso_glo/(?P<year>\d{4})$",
        MonthlyPage
    )
    c_daily = URL(
        r"/consommation/conso_glo/(?P<year>\d{4})/(?P<month>\d{2})$",
        DailyPage
    )
    c_hourly = URL(
        r"/consommation/conso_glo/(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})$",
        HourlyPage
    )

    # Max power sensor URLs
    p_monthly = URL(
        r"/consommation/puissance_max/(?P<year>\d{4})$",
        MonthlyPage
    )
    p_daily = URL(
        r"/consommation/puissance_max/(?P<year>\d{4})/(?P<month>\d{2})$",
        DailyPage
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
        "hourly": "par demie-heure ou quart d'heure",
    }

    maxpower_periods = {
        "monthly": "mensuelle",
        "daily": "quotidienne",
    }

    def iter_sensors(self, id, pattern=None):
        g = find_object(self.iter_gauges(), id=id)
        assert g

        sensors = []
        sensors.extend([
            GaugeSensor.from_dict({
                "id": f"{id}.c.{subid}",
                "name": f"Consommation électrique {name}",
                "unit": "kWh",
                "gaugeid": id,
            })
            for subid, name in self.consumption_periods.items()
        ])
        sensors.extend([
            GaugeSensor.from_dict({
                "id": f"{id}.p.{subid}",
                "name": f"Puissance max {name}",
                "unit": "kVA",
                "gaugeid": id,
            })
            for subid, name in self.maxpower_periods.items()
        ])
        return sensors

    @need_login
    def iter_sensor_history(self, id):
        pdl, sensor_type, subid = id.split(".")
        assert sensor_type in ("c", "p")
        if sensor_type == "c":
            yield from self._iter_sensor_history_c(subid)
        elif sensor_type == "p":
            yield from self._iter_sensor_history_p(subid)

    def _iter_sensor_history_c(self, subid):
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
            getattr(self, "c_" + subid).go(**url_args)

        for measure in self.page.iter_sensor_history("conso"):
            if measure.date.date() > max_date:
                continue
            yield measure

    def _iter_sensor_history_p(self, subid):
        assert subid in ("monthly", "daily")

        # can't fetch stats of today, use yesterday (and the corresponding month/year)
        max_date = datetime.date.today() - datetime.timedelta(days=1)

        url_args = {}
        for unit in ("year", "month", "day"):
            if subid[0] != unit[0]:
                url_args[unit] = str(getattr(max_date, unit)).zfill(2)
            else:
                break

        getattr(self, "p_" + subid).go(**url_args)

        for measure in self.page.iter_sensor_history("puissance_max"):
            if measure.date.date() > max_date:
                continue
            yield measure
