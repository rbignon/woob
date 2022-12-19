# Copyright(C) 2022 Budget Insight
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

from unittest import TestCase

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanText, Eval
from woob.browser.pages import JsonPage
from woob.capabilities.base import BaseObject, StringField
from woob.tools.json import json


class TestElements(TestCase):
    def test_iterate_over_dict_elements(self):
        class MyObject(BaseObject):
            label = StringField('Label of the object')

        class MyResponse:
            pass

        response = MyResponse()
        response.url = 'https://example.org/objects'
        response.headers = {
            'content-type': 'application/json; charset=utf-8',
        }
        response.text = json.dumps({
            'objects': {
                '1': {
                    'id': '1',
                    'label': 'hello'
                },
                '2': {
                    'id': '2',
                    'label': 'world',
                },
            },
        })

        class MyBrowser:
            pass

        browser = MyBrowser()
        browser.logger = None

        class MyPage(JsonPage):
            @method
            class iter_objects(DictElement):
                item_xpath = 'objects'

                class item(ItemElement):
                    klass = MyObject

                    obj_id = Dict('id')
                    obj_label = CleanText(Dict('label'))

        page = MyPage(browser, response)
        objects = list(page.iter_objects())
        assert len(objects) == 2
        assert objects[0].id == '1'
        assert objects[0].label == 'hello'
        assert objects[1].id == '2'
        assert objects[1].label == 'world'

    def test_use_filter_as_item_condition(self):
        """Use a filter as the 'condition' property of list and item elements."""
        class MyObject(BaseObject):
            label = StringField('Label of the object')

        class MyResponse:
            pass

        response = MyResponse()
        response.url = 'https://example.org/objects'
        response.headers = {
            'content-type': 'application/json; charset=utf-8',
        }
        response.text = json.dumps({
            'objects': {
                '1': {
                    'id': '1',
                    'label': 'hello',
                    'should_be_even': 2,
                },
                '2': {
                    'id': '2',
                    'label': 'world',
                    'should_be_even': 3,
                },
                '3': {
                    'id': '3',
                    'label': 'universe',
                    'should_be_even': 4,
                },
            },
        })

        class MyBrowser:
            pass

        browser = MyBrowser()
        browser.logger = None

        class MyItemElement(ItemElement):
            klass = MyObject

            condition = Eval(
                lambda x: x % 2 == 0,
                Dict('should_be_even'),
            )

            obj_id = Dict('id')
            obj_label = CleanText(Dict('label'))

        class MyPage(JsonPage):
            @method
            class iter_objects(DictElement):
                item_xpath = 'objects'

                condition = Dict('objects', default=None)

                item = MyItemElement

            @method
            class iter_other_objects(DictElement):
                item_xpath = 'other_objects'

                condition = Dict('other_objects', default=None)

                item = MyItemElement

        page = MyPage(browser, response)
        objects = list(page.iter_objects())
        assert len(objects) == 2
        assert objects[0].id == '1'
        assert objects[0].label == 'hello'
        assert objects[1].id == '3'
        assert objects[1].label == 'universe'

        objects = list(page.iter_other_objects())
        assert len(objects) == 0
