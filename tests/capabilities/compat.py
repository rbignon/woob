# -*- coding: utf-8 -*-
# Copyright(C) 2022 woob project
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

import pytest


def test_person():
    from woob.capabilities.profile import Person

    p = Person()
    p.maiden_name = "foo"
    assert p.maiden_name == "foo"
    assert p.birth_name == "foo"


@pytest.mark.parametrize(
    "old,new",
    [
        ("company_siren", "siren"),
        ("company_name", "name"),
        ("job_activity_area", "activity_area"),
    ]
)
def test_person_company(old, new):
    from woob.capabilities.profile import Person

    p = Person()
    setattr(p, old, "1234")
    assert getattr(p, old) == "1234"
    assert getattr(p.company, new) == "1234"
