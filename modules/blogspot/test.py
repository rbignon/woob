# Copyright(C) 2017      Vincent A
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

from woob.tools.test import BackendTest, skip_without_config


class BlogspotTest(BackendTest):
    MODULE = "blogspot"

    @skip_without_config("url")
    def test_blog(self):
        threads = list(self.backend.iter_threads())
        assert threads

        for thr in threads:
            assert thr.title
            assert thr.date
            assert thr.root
            assert thr.root.title
            assert not thr.root.content

        msg = threads[0].root
        self.backend.fillobj(msg)

        assert msg.children
        for sub in msg.children:
            assert sub.date
            assert sub.url
            assert not sub.children

            self.backend.fillobj(sub)
            assert sub.content
