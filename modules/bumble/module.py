# Copyright(C) 2022      Roger Philibert
#
# This file is part of a woob module.
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

from time import sleep

from woob.capabilities.dating import CapDating, Optimization
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import Value, ValueTransient
from woob.tools.log import getLogger

from .browser import BumbleBrowser


__all__ = ['BumbleModule']


class ProfilesWalker(Optimization):
    def __init__(self, sched, storage, browser, city: str):
        self._sched = sched
        self._storage = storage
        self._browser = browser
        self._city = city
        self._logger = getLogger('walker', browser.logger)

        self._view_cron = None

    def start(self):
        self._view_cron = self._sched.schedule(1, self.view_profile)
        return True

    def stop(self):
        self._sched.cancel(self._view_cron)
        self._view_cron = None
        return True

    def set_config(self, params):
        pass

    def is_running(self):
        return self._view_cron is not None

    def view_profile(self):
        next_try = 30
        try:
            for user in self._browser.iter_encounters():
                if not self._city or self._city in user['distance_long']:
                    like = True
                    self._logger.info('Like %s' % user['name'])
                else:
                    like = False
                    self._logger.info('Unlike %s (%s)' % (user['name'], user['distance_long']))

                if self._browser.like_user(user, like):
                    self._logger.info('Match with %s' % user['name'])

                sleep(3)

        finally:
            if self._view_cron is not None:
                self._view_cron = self._sched.schedule(next_try, self.view_profile)


class BumbleModule(Module, CapDating):
    NAME = 'bumble'
    DESCRIPTION = 'Bumble dating mobile application'
    MAINTAINER = 'Roger Philibert'
    EMAIL = 'roger.philibert@gmail.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.3.1'
    CONFIG = BackendConfig(Value('phone',  label='Phone number'),
                           Value('city', label='City where to like people (optional)', required=False),
                           ValueTransient('pincode')
                           )

    BROWSER = BumbleBrowser

    def create_default_browser(self):
        return self.create_browser(self.config)

    # ---- CapDating methods -----------------------

    def init_optimizations(self):
        self.browser.login()
        self.add_optimization('PROFILE_WALKER', ProfilesWalker(self.weboob.scheduler, self.storage, self.browser, self.config['city'].get()))
