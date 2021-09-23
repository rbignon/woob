# -*- coding: utf-8 -*-

# Copyright(C) 2021 Vincent A
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


class TinyViewTest(BackendTest):
    MODULE = "tinyview"

    def test_threads(self):
        n = -1
        ids = set()

        for thread, n in zip(self.backend.iter_threads(), range(20)):  # noqa
            assert thread.id
            assert thread.title
            assert thread.title == thread.root.title
            assert thread.url

            assert thread.root.date
            assert thread.root.sender
            assert thread.root.url
            assert thread.root.content
            assert "<figure" in thread.root.content

            ids.add(thread.id)

        assert n > -1
        assert len(ids) == n + 1
