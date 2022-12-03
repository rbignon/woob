# -*- coding: utf-8 -*-

# Copyright(C) 2021 Romain Bignon
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

from tempfile import mkstemp
from os import remove

from woob.tools.application.formatters.json import (
    JsonFormatter, JsonLineFormatter,
)
from woob.tools.application.formatters.table import TableFormatter


def formatter_test_output(Formatter, obj):
    """
    Formats an object and returns output as a string.
    For test purposes only.
    """
    _, name = mkstemp()
    fmt = Formatter()
    fmt.outfile = name
    fmt.format(obj)
    fmt.flush()
    with open(name) as f:
        res = f.read()
    remove(name)
    return res


def test_json():
    assert formatter_test_output(JsonFormatter, {'foo': 'bar'}) == '[{"foo": "bar"}]\n'
    assert formatter_test_output(JsonLineFormatter, {'foo': 'bar'}) == '{"foo": "bar"}\n'
    assert formatter_test_output(JsonLineFormatter, {'foo': 'bar'}) == '{"foo": "bar"}\n'


def test_table():
    assert formatter_test_output(TableFormatter, {'foo': 'bar'}) == (
        '┌─────┐\n'
        '│ Foo │\n'
        '├─────┤\n'
        '│ bar │\n'
        '└─────┘\n'
    )
