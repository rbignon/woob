# -*- coding: utf-8 -*-

# Copyright(C) 2022 woob project
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

from datetime import timedelta

from dateutil import parser, tz

from woob.exceptions import (
    NeedInteractiveFor2FA, BrowserInteraction,
)
from woob.tools.date import now_as_utc
from woob.tools.value import Value

from .browsers import LoginBrowser, StatesMixin


__all__ = ["TwoFactorBrowser"]


class TwoFactorBrowser(LoginBrowser, StatesMixin):
    # period to keep the same state
    # it is different from STATE_DURATION which updates the expire date at each dump
    TWOFA_DURATION = None

    INTERACTIVE_NAME = 'request_information'
    # dict of config keys and methods used for double authentication
    # must be set up in the init to handle function pointers
    AUTHENTICATION_METHODS = {}

    # list of cookie keys to clear before dumping state
    COOKIES_TO_CLEAR = ()

    # login can also be done with credentials without 2FA
    HAS_CREDENTIALS_ONLY = False

    # Skip locate_browser if one of the config values is defined (for example
    # its useful to prevent calling twice the url that sends an OTP)
    SKIP_LOCATE_BROWSER_ON_CONFIG_VALUES = ()

    def __init__(self, config, *args, **kwargs):
        super(TwoFactorBrowser, self).__init__(*args, **kwargs)
        self.config = config
        self.is_interactive = config.get(self.INTERACTIVE_NAME, Value()).get() is not None
        self.twofa_logged_date = None

    def get_expire(self):
        expires_dates = [now_as_utc() + timedelta(minutes=self.STATE_DURATION)]

        if self.twofa_logged_date and self.TWOFA_DURATION is not None:
            expires_dates.append(self.twofa_logged_date + timedelta(minutes=self.TWOFA_DURATION))

        return str(max(expires_dates).replace(microsecond=0))

    def dump_state(self):
        self.clear_not_2fa_cookies()
        state = super(TwoFactorBrowser, self).dump_state()
        if self.twofa_logged_date:
            state['twofa_logged_date'] = str(self.twofa_logged_date)

        return state

    def should_skip_locate_browser(self):
        for key in self.SKIP_LOCATE_BROWSER_ON_CONFIG_VALUES:
            value = self.config.get(key)
            if value is None:
                continue

            if value.get() != value.default:
                return True

        return False

    def locate_browser(self, state):
        if self.should_skip_locate_browser():
            return

        super().locate_browser(state)

    def load_state(self, state):
        super(TwoFactorBrowser, self).load_state(state)
        self.twofa_logged_date = None
        if state.get('twofa_logged_date') not in (None, '', 'None'):
            twofa_logged_date = parser.parse(state['twofa_logged_date'])
            if not twofa_logged_date.tzinfo:
                twofa_logged_date = twofa_logged_date.replace(tzinfo=tz.tzlocal())
            self.twofa_logged_date = twofa_logged_date

    def init_login(self):
        """
        Abstract method to implement initiation of login on website.

        This method should raise an exception.

        SCA exceptions :
        - AppValidation for polling method
        - BrowserQuestion for SMS method, token method etc.

        Any other exceptions, default to BrowserIncorrectPassword.
        """
        raise NotImplementedError()

    def clear_init_cookies(self):
        # clear cookies to avoid some errors
        self.session.cookies.clear()

    def clear_not_2fa_cookies(self):
        # clear cookies that we don't need for 2FA
        for cookie_key in self.COOKIES_TO_CLEAR:
            if cookie_key in self.session.cookies:
                del self.session.cookies[cookie_key]

    def check_interactive(self):
        if not self.is_interactive:
            raise NeedInteractiveFor2FA()

    def do_double_authentication(self):
        """
        This method will check AUTHENTICATION_METHODS
        to dispatch to the right handle_* method.

        If no backend configuration could be found,
        it will then call init_login method.
        """

        def clear_sca_key(config_key):
            value = self.config.get(config_key)
            if value is not None:
                value.set(value.default)

        assert self.AUTHENTICATION_METHODS, 'There is no config for the double authentication.'

        for config_key, handle_method in self.AUTHENTICATION_METHODS.items():
            config_value = self.config.get(config_key, Value())
            if not config_value:
                continue

            setattr(self, config_key, config_value.get())
            if getattr(self, config_key):
                try:
                    handle_method()
                except BrowserInteraction:
                    # If a BrowserInteraction is raised during the handling of the sca_key,
                    # we need to clear it before restarting the process to prevent it to block
                    # other sca_keys handling.
                    clear_sca_key(config_key)
                    raise

                self.twofa_logged_date = now_as_utc()

                # cleaning authentication config keys
                for config_key in self.AUTHENTICATION_METHODS.keys():
                    clear_sca_key(config_key)

                break
        else:
            if not self.HAS_CREDENTIALS_ONLY:
                self.check_interactive()

            self.clear_init_cookies()
            self.init_login()

    do_login = do_double_authentication
