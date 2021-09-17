# -*- coding: utf-8 -*-

# Copyright(C) 2010-2021 Romain Bignon
#
# This file is part of woob.
#
# woob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# woob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with woob. If not, see <http://www.gnu.org/licenses/>.

from woob.tools.date import real_datetime, closest_date


def test_closest():
    dt = real_datetime
    range1 = [dt(2012,12,20), dt(2013,1,10)]

    assert closest_date(dt(2012,12,15), *range1) == dt(2012,12,15)
    assert closest_date(dt(2000,12,15), *range1) == dt(2012,12,15)
    assert closest_date(dt(2020,12,15), *range1) == dt(2012,12,15)

    assert closest_date(dt(2013,1,15), *range1) == dt(2013,1,15)
    assert closest_date(dt(2000,1,15), *range1) == dt(2013,1,15)
    assert closest_date(dt(2020,1,15), *range1) == dt(2013,1,15)

    assert closest_date(dt(2013,1,1), *range1) == dt(2013,1,1)
    assert closest_date(dt(2000,1,1), *range1) == dt(2013,1,1)
    assert closest_date(dt(2020,1,1), *range1) == dt(2013,1,1)

    range2 = [dt(2012,12,20), dt(2014,1,10)]
    assert closest_date(dt(2012,12,15), *range2) == dt(2013,12,15)
    assert closest_date(dt(2014,1,15), *range2) == dt(2013,1,15)
