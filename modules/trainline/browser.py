# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from weboob.browser import URL
from weboob.browser.browsers import LoginBrowser, need_login
from weboob.exceptions import BrowserIncorrectPassword
from weboob.browser.exceptions import ClientError

from .pages import SigninPage, UserPage, DocumentsPage


class TrainlineBrowser(LoginBrowser):
    BASEURL = 'https://www.thetrainline.com'

    signin = URL(r'/login-service/api/login', SigninPage)
    user_page = URL(r'/login-service/v5/user', UserPage)
    documents_page = URL(r'/my-account/api/bookings/past', DocumentsPage)

    def __init__(self, login, password, *args, **kwargs):
        super(TrainlineBrowser, self).__init__(login, password, *args, **kwargs)
        self.session.headers['X-Requested-With'] = 'XMLHttpRequest'

    def do_login(self):
        # we need to set the cookie _abck before to go on the site else we have a timed out
        self.session.cookies.set(
            '_abck',
            'DE150AD2F45BF2BF6819EC06C0AE23C8~-1~YAAQiCgRAmLeL8x3AQAADjeh9wVg/vRae6GVsIalPsslBevAkThKngnL76z0WG/VQH/INclzlqTnMC83UBplxa/x6TwZsk4D8dxEhC7uf7NMVDoZ46+vd6IdWAaEbARLhd/zJ6hzN0HUQTOEYLBM0EwDVRG39cnGoH977GILri1W4UbrnU4c6fWxHgGl9OM1dk+Ru/rhPJe1ZSnH3+a+ahzpsXremV84QYLwsnybHREwrqMkxXWQSXt3d0eorPIGr5A5U7152vGY3ZXbfKQvHEu9vMj51E4uA8jM/q0EL5rMshht+0xF2uoiaX9NqQhHW8DhSUSvlLPZC8kiffI+E/PTqy97xJTOr5m6hkshawamXtiFK1KXDZLzSV6nIQ3LUow=~-1~-1~-1',
        )
        # set some cookies
        self.go_home()

        try:
            self.signin.go(json={'email': self.username, 'password': self.password})
        except ClientError as e:
            if e.response.status_code == 403:
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
