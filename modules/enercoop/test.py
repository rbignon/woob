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

from __future__ import unicode_literals


from woob.tools.test import BackendTest


class EnercoopTest(BackendTest):
    MODULE = 'enercoop'

    def test_subs(self):
        subs = list(self.backend.iter_subscription())
        assert subs
        sub = subs[0]
        assert subs[0].id
        assert subs[0].label

        docs = list(self.backend.iter_documents(sub))
        assert docs

        doc = docs[0]
        assert doc.id
        assert doc.label
        assert doc.total_price
        assert doc.url

    def test_gauge(self):
        # for now, only one gauge is returned, update the test when more are implemented
        gauge, = list(self.backend.iter_gauges())
        sensors = list(self.backend.iter_sensors(gauge.id))

        # TODO update if max power sensors are implemented
        assert len(sensors) == 4
        assert any(sensor.id.endswith(".c.yearly") for sensor in sensors)
        assert sensors[0].name
        assert sensors[0].unit == "kWh"
        assert sensors[0].gaugeid == gauge.id

        measures = [
            measure
            for _, measure in zip(range(10), self.backend.iter_gauge_history(sensors[0].id))
        ]
        assert len(measures)
        assert any(measure.level > 0 for measure in measures)
        assert len(set(measure.date for measure in measures)) == len(measures)
