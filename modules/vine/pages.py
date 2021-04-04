# -*- coding: utf-8 -*-

# Copyright(C) 2015      P4ncake
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

from woob.capabilities.video import BaseVideo

from woob.browser.elements import ItemElement, DictElement, method
from woob.browser.pages import JsonPage
from woob.browser.filters.standard import Regexp
from woob.browser.filters.json import Dict


class SearchPage(JsonPage):
    @method
    class iter_videos(DictElement):
        item_xpath ='data/records'
        class item(ItemElement):
            klass = BaseVideo

            obj_id = Regexp(Dict('shareUrl'), '/([a-zA-Z0-9]*)$')
            obj_title = Dict('description')
            obj_url = Dict('videoUrl')
            obj_ext = Regexp(Dict('videoUrl'), r'.*\.(.*?)\?.*')
            obj_author = Dict('username')

class PostPage(JsonPage):
    @method
    class get_video(ItemElement):
        klass = BaseVideo

        obj_id = Dict('postId')
        obj_url = Dict('videoUrl')
