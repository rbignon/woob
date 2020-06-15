# -*- coding: utf-8 -*-

# Copyright(C) 2020 Johann Broudin
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

import re

from lxml import html


def radios(webradios, radiosjs):
    radiosjs_re = (
            r'{id:(?P<id>\d+),'
            r'id_radio:(?P<id_radio>\d+),'
            r'type:"[^"]*",'
            r'name:"(?P<name>[^"]*)",'
            r'hls_source:"(?P<hls_source>[^"]*)",'
            r'source:"(?P<source>[^"]*)"'
            )
    webradios_xpath = '//ul/li[@class="brick"]/div/div[@data-id="%s"]/ancestor::li/div/h3/text()'

    radios = {}
    tree = html.fromstring(webradios.content)
    for m in re.finditer(radiosjs_re, radiosjs.text):
        radios[m.group('name')] = {'radio_id': m.group('id_radio'),
                                   'name': m.group('name'),
                                   'hls_source': m.group('hls_source'),
                                   'source': m.group('source'),
                                   'title': tree.xpath(webradios_xpath % (m.group('id_radio')))[0]}

    return radios


def current(r):
    artist = ''
    title = ''
    info = r.json()['root_tab']['event']
    if len(info) > 0:
        artist = info[0]['artist']
        title = info[0]['title']

    return artist, title


def description(r):
    description = ''
    info = r.json()['root_tab']['events']
    if len(info) > 0:
        description = "%s - %s" % (info[0]['title'], info[0]['tab_foreign_type']['resum'])

    return description
