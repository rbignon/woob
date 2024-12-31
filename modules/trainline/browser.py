# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
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

from requests import ReadTimeout

from woob.browser import URL
from woob.browser.browsers import LoginBrowser, need_login
from woob.browser.exceptions import ClientError
from woob.exceptions import BrowserIncorrectPassword
from woob.tools.decorators import retry

from .akamai import AkamaiMixin
from .pages import DocumentsPage, HomePage, SigninPage, UserPage


SENSOR_DATA = (
    "7a74G7m23Vrp0o5c9361761.75"
    "-1,2,-94,-100,{user_agent},uaend,11059,20100101,fr,Gecko,0,0,0,0,409191,9985678,"
    "1920,1018,1920,1080,1920,880,1920,,cpen:0,i1:0,dm:0,cwen:0,non:1,opc:0,fc:1,sc:0,"
    "wrc:1,isc:169,vib:1,bat:0,x11:0,x12:1,4843,0.984818677492,831529992838.5,0,loc:"
    "-1,2,-94,-131,"
    "-1,2,-94,-101,do_en,dm_en,t_dis"
    "-1,2,-94,-105,0,0,0,0,1885,1885,0;0,0,0,0,1676,1676,0;0,0,0,0,"
    "3006,3006,0;0,-1,0,0,3759,3759,1;0,-1,0,0,3630,3630,0;"
    "-1,2,-94,-102,0,0,0,0,1885,1885,0;0,0,0,0,1676,1676,0;0,0,0,0,"
    "3006,3006,0;0,-1,0,0,3759,3759,1;0,-1,0,0,3630,3630,0;"
    "-1,2,-94,-108,"
    "-1,2,-94,-110,"
    "-1,2,-94,-117,"
    "-1,2,-94,-111,"
    "-1,2,-94,-109,"
    "-1,2,-94,-114,"
    "-1,2,-94,-103,"
    "-1,2,-94,-112,https://www.thetrainline.com/"
    "-1,2,-94,-115,1,32,32,0,0,0,0,2215,0,1663059985677,7,17790,0,0,2965,0,0,2215,0,0,{_abck}"
    ",38263,546,1956719195,25543097,PiZtE,91983,92,0,-1"
    "-1,2,-94,-106,9,1"
    "-1,2,-94,-119,-1"
    "-1,2,-94,-122,0,0,0,0,1,0,0"
    "-1,2,-94,-123,"
    "-1,2,-94,-124,"
    "-1,2,-94,-126,"
    "-1,2,-94,-127,11133333331333333333"
    "-1,2,-94,-70,-1279939100;-324940575;dis;;true;true;true;-120;true;24;24;true;false;1"
    "-1,2,-94,-80,5377"
    "-1,2,-94,-116,2426519511"
    "-1,2,-94,-118,93260"
    "-1,2,-94,-129,,,0,,,,0"
    "-1,2,-94,-121,;3;240;0"
)


class TrainlineBrowser(LoginBrowser, AkamaiMixin):
    BASEURL = 'https://www.thetrainline.com'

    home = URL(r'/$', HomePage)
    signin = URL(r'/login-service/api/login', SigninPage)
    user_page = URL(r'/login-service/v5/user', UserPage)
    documents_page = URL(r'/my-account/api/bookings/past', DocumentsPage)

    @retry(ReadTimeout)
    def do_login(self):
        # set some cookies
        self.go_home()

        # set X-Requested-With AFTER go_home(), to get the akamai url in html
        # else it is missing
        # this url is used by AkamaiMixin to resolve challenge
        self.session.headers['X-Requested-With'] = 'XMLHttpRequest'

        if self.session.cookies.get('_abck'):
            akamai_url = self.page.get_akamai_url()
            if akamai_url:
                # because sometimes this url is missing
                # in that case, we simply don't resolve challenge
                self.open(akamai_url)  # call this url to let akamai think we have resolved its challenge
                sensor_data = SENSOR_DATA.replace('{user_agent}', self.session.headers['User-Agent'])
                sensor_data = sensor_data.replace('{_abck}', self.session.cookies['_abck'])
                data = {
                    "sensor_data": sensor_data
                }
                self.open(akamai_url, json=data)

        try:
            self.signin.go(json={'email': self.username, 'password': self.password})
        except ClientError as e:
            if e.response.status_code in (400, 403):
                error = e.response.json().get('message')
                if 'invalid_grant' in error:
                    raise BrowserIncorrectPassword(error)
            raise

        self.user_page.go()

    @need_login
    def get_subscription_list(self):
        self.user_page.stay_or_go()
        yield self.page.get_subscription()

    @need_login
    def iter_documents(self, subscription):
        self.documents_page.go()
        return self.page.iter_documents(subid=subscription.id)
