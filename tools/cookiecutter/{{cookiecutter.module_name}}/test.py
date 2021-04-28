# -*- coding: utf-8 -*-

# Copyright(C) {{cookiecutter.year}} {{cookiecutter.full_name}}
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

from woob.tools.test import BackendTest


class TwitterTest(BackendTest):
    MODULE = "{{cookiecutter.module_name}}"

    def test_something(self):
        n = -1
        for obj, n in zip(self.backend.iter_something(), range(20)):
            assert obj.label
            assert obj.price
            assert obj.url.startswith(self.backend.browser.BASEURL)

        assert n > -1
