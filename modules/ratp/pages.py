# -*- coding: utf-8 -*-

# Copyright(C) 2017      Phyks (Lucas Verney)
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

import datetime

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import Attr
from woob.browser.filters.standard import CleanText, Eval
from woob.browser.pages import HTMLPage
from woob.capabilities.gauge import Gauge, GaugeMeasure


NORMAL = 0.0
NORMAL_AND_WORK = -1.0
ALERT = -2.0
ALERT_AND_WORK = -3.0
CRITICAL = -4.0
CRITICAL_AND_WORK = -5.0


class MeteoPage(HTMLPage):
    @method
    class fetch_lines(ListElement):
        item_xpath = '//*[@class="lignes"]/div'

        class Line(ItemElement):
            klass = Gauge

            obj_city = "Paris"
            obj_object = "Current status"
            obj_id = Attr(".", attr="id")
            obj_name = Eval(lambda x: (x.replace("ligne_", "").replace("_", " ").title().replace("Rer", "RER")), obj_id)

    @method
    class fetch_status(ListElement):
        item_xpath = '//div[@id="box"]'

        class Line(ItemElement):
            klass = GaugeMeasure

            def obj_level(self):
                classes = Attr('//*[@class="lignes"]//div[@id="%s"]' % self.env["line"], attr="class")(self)
                classes = classes.split()
                if "perturb_critique_trav" in classes:
                    return CRITICAL_AND_WORK
                elif "perturb_critique" in classes:
                    return CRITICAL
                elif "perturb_alerte_trav" in classes:
                    return ALERT_AND_WORK
                elif "perturb_alerte" in classes:
                    return ALERT
                elif "perturb_normal_trav" in classes:
                    return NORMAL_AND_WORK
                elif "perturb_normal" in classes:
                    return NORMAL

            def obj_alarm(self):
                title = CleanText(
                    '//*[@class="lignes"]//div[@id="%s"]//div[@class="popin_hover_title"]' % self.env["line"]
                )(self)
                details = CleanText(
                    '//*[@class="lignes"]//div[@id="%s"]//div[@class="popin_hover_text"]//span[1]' % self.env["line"]
                )(self)
                return "%s: %s" % (title, details)

            def obj_date(self):
                time = CleanText('//span[@id="refresh_time"]')(self)
                time = [int(t) for t in time.split(":")]
                now = datetime.datetime.now()
                now.replace(hour=time[0], minute=time[1])
                return now
