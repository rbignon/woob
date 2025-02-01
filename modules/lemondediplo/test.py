# Copyright(C) 2021      Bezleputh
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

from datetime import datetime

from woob.capabilities.messages import Thread
from woob.tools.test import BackendTest


class LemondediploTest(BackendTest):
    MODULE = "lemondediplo"

    def generic_test(self):
        _ = list(self.backend.iter_threads())
        assert len(_)
        t = self.backend.get_thread(_[0].id)
        self.assertTrue(t.root is not None)

    def test_blogs(self):
        _ = list(self.backend.iter_resources([Thread], ["blogs"]))
        assert len(_)

        _ = self.backend.fillobj(_[-1])

        self.assertTrue(_.root)
        self.assertTrue(_.date)
        self.assertTrue(_.title)
        self.assertTrue(_.root.content)

    def test_archives(self):
        _ = list(self.backend.iter_resources([Thread], [datetime.today().strftime("%Y-%m")]))
        assert len(_)

        _ = self.backend.fillobj(_[-1])

        self.assertTrue(_.root)
        self.assertTrue(_.date)
        self.assertTrue(_.title)
        self.assertTrue(_.root.content)
