# -*- coding: utf-8 -*-

# Copyright(C) 2013      dud
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

from woob.tools.test import BackendTest


class VelibTest(BackendTest):
    MODULE = 'jcvelaux'

    def test_velib(self):
        l = list(self.backend.iter_gauges())
        self.assertTrue(len(l) > 0)

        gauge = l[0]
        s = list(self.backend.iter_sensors(gauge))
        self.assertTrue(len(s) > 0)

        sensor = s[0]
        self.assertTrue(self.backend.get_last_measure(sensor.id) is not None)
