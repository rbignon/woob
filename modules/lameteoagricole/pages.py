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

from datetime import date, datetime, time, timedelta
from urllib.parse import quote

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.standard import CleanText, Field
from woob.browser.pages import HTMLPage, XMLPage
from woob.capabilities.weather import City, Current, Direction, Forecast, Temperature


class CitiesPage(XMLPage):
    ENCODING = "utf-8"

    @method
    class iter_cities(ListElement):
        item_xpath = "//suggest"

        class item(ItemElement):
            klass = City

            obj_name = CleanText(".")

            def obj_id(self):
                return quote(Field("name")(self))


def temp(v):
    t = Temperature()
    t.unit = "C"
    t.value = v
    return t


class WeatherPage(HTMLPage):
    def fill_base(self, obj, n):
        obj.text = self.get_img_cell(self.titles["Temps sensible"], n)

        if "Humidité relative moyenne" in self.titles:
            humidity = self.get_cell(self.titles["Humidité relative moyenne"], n)
        else:
            humidity = self.get_cell(self.titles["Humidité relative"], n)
        obj.humidity = float(humidity.strip("%")) / 100

        direction = self.get_cell(self.titles["Direction du vent"], n).replace("O", "W")
        obj.wind_direction = getattr(Direction, direction)

        if "Vitesse du vent" in self.titles:
            speed_text = self.get_cell(self.titles["Vitesse du vent"], n)
        elif "Vitesse Moy. du vent" in self.titles:
            speed_text = self.get_cell(self.titles["Vitesse Moy. du vent"], n)
        else:
            speed_text = self.get_cell(self.titles["Vitesse moyenne du vent"], n)
        obj.wind_speed = float(speed_text.replace("km/h", "").strip())

        if "Probabilité de précipitations" in self.titles:
            txt = self.get_cell(self.titles["Probabilité de précipitations"], n)
            obj.precipitation_probability = float(txt.strip("<%")) / 100

        if "Nébulosité" in self.titles:
            txt = self.get_cell(self.titles["Nébulosité"], n).rstrip("%")
            obj.cloud = int(round(float(txt) / 100 * 8))


class HourPage(WeatherPage):
    def get_cell(self, row, col):
        return CleanText(f'//table[@id="meteoHour"]/tr[{row + 1}]/td[{col + 1}]')(self.doc)

    def get_img_cell(self, row, col):
        return CleanText(f'//table[@id="meteoHour"]/tr[{row + 1}]/td[{col + 1}]/img/@alt')(
            self.doc
        )

    def get_current(self):
        fore = next(iter(self.iter_forecast()))
        ret = Current()
        for f in ("date", "text", "wind_direction", "wind_speed", "humidity"):
            setattr(ret, f, getattr(fore, f))
        ret.temp = fore.high
        return ret

    def iter_forecast(self):
        d = date.today()

        self.titles = {}
        for n, tr in enumerate(self.doc.xpath('//table[@id="meteoIntit"]/tr')):
            self.titles[CleanText(".")(tr)] = n

        day_str = None
        for n in range(len(self.doc.xpath('//table[@id="meteoHour"]/tr[1]/td'))):
            obj = Forecast()

            t = time(int(self.get_cell(self.titles["Heure"], n).rstrip("h")), 0)

            new_day_str = self.get_cell(self.titles["Jour"], n)
            if day_str is not None and day_str != new_day_str:
                d += timedelta(1)
            day_str = new_day_str
            obj.date = datetime.combine(d, t)

            obj.low = obj.high = temp(float(self.get_cell(self.titles["T° (ressentie)"], n).split("°")[0]))
            self.fill_base(obj, n)

            yield obj


class Days5Page(WeatherPage):
    def get_cell(self, row, col):
        return CleanText(f'//table[@id="meteo2"]/tr[2]/td[{col + 1}]/table/tr[{row + 1}]/td')(
            self.doc
        )

    def get_img_cell(self, row, col):
        return CleanText(
            f'//table[@id="meteo2"]/tr[2]/td[{col + 1}]/table/tr[{row + 1}]/td//img/@alt'
        )(self.doc)

    def iter_forecast(self):
        d = date.today()

        self.titles = {}
        for n, tr in enumerate(self.doc.xpath('//table[@id="meteo2"]/tr[2]/td[1]/table/tr')):
            self.titles[CleanText(".")(tr)] = n

        for n in range(1, len(self.doc.xpath('//table[@id="meteo2"]/tr[1]/td'))):
            obj = Forecast()
            obj.low = temp(float(self.get_cell(self.titles["Température Mini"], n).rstrip("°")))

            high_text = self.get_cell(self.titles["Température Maxi"], n).rstrip("°")
            if high_text != "-":
                obj.high = temp(float(high_text))

            obj.date = d
            self.fill_base(obj, n)

            d += timedelta(1)
            yield obj


class Days10Page(WeatherPage):
    def get_cell(self, row, col):
        return CleanText(f'(//table[@id="meteo2"]//td/table)[{col + 1}]/tr[{row + 1}]/td')(
            self.doc
        )

    def get_img_cell(self, row, col):
        return CleanText(
            f'(//table[@id="meteo2"]//td/table)[{col + 1}]/tr[{row + 1}]/td//img/@alt'
        )(self.doc)

    def iter_forecast(self):
        d = date.today() + timedelta(5)

        self.titles = {}
        for n, tr in enumerate(self.doc.xpath('(//table[@id="meteo2"]//td/table)[1]/tr/td')):
            self.titles[CleanText(".")(tr)] = n

        cols = len(self.doc.xpath('//table[@id="meteo2"]//td/table'))
        for n in range(1, cols):
            obj = Forecast()
            obj.low = temp(float(self.get_cell(self.titles["Température Mini"], n).rstrip("°C")))
            obj.high = temp(float(self.get_cell(self.titles["Température Maxi"], n).rstrip("°C")))
            obj.date = d
            self.fill_base(obj, n)

            d += timedelta(1)
            yield obj
