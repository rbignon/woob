# Copyright(C) 2023 Powens
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

# flake8: compatible

import pytest

from woob.tools.backend import BackendConfig
from woob.tools.value import Value, ValuesDict


@pytest.mark.parametrize("cls", (ValuesDict, BackendConfig))
def test_with_values(cls):
    """Test creating copies of dictionaries using with_values."""
    first_obj = cls(
        Value("a", label="A value"),
        Value("b", label="B value"),
    )
    second_obj = first_obj.with_values(
        Value("a", label="Different A value"),
        Value("c", label="C value"),
    )

    # Check that the first object hasn't changed, and that the second
    # object indeed is different.
    assert second_obj is not first_obj
    assert set(first_obj) == {"a", "b"}
    assert first_obj["a"].label == "A value"

    # Check that the second object is how we want it.
    assert set(second_obj) == {"a", "b", "c"}
    assert second_obj["a"] is not first_obj["a"]
    assert second_obj["b"] is first_obj["b"]  # No unnecessary copies.
    assert second_obj["a"].label == "Different A value"


@pytest.mark.parametrize("cls", (ValuesDict, BackendConfig))
def test_without_values(cls):
    """Test creating copies of dictionaries using without_values."""
    first_obj = cls(
        Value("a", label="A value"),
        Value("b", label="B value"),
    )
    second_obj = first_obj.without_values("b")

    # Check that the first object hasn't changed, and that the second
    # object indeed is different.
    assert second_obj is not first_obj
    assert set(first_obj) == {"a", "b"}

    # Check that the second object is how we want it.
    assert set(second_obj) == {"a"}
    assert second_obj["a"] is first_obj["a"]
