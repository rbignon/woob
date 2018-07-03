# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
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

import hashlib
import json
import logging
import re
import time

from weboob.exceptions import BrowserQuestion
from weboob.browser import URL, need_login, PagesBrowser, StatesMixin
from weboob.browser.selenium import (
    SeleniumBrowser, StablePageCondition, AnyCondition, IsHereCondition,
    webdriver, SubSeleniumMixin,
)
from weboob.tools.capabilities.bank.transactions import sorted_transactions
from weboob.tools.value import Value
from weboob.tools.decorators import retry
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException

from .pages import (
    LoginPage1, FinalLoginPage, LoginPageOtp, LoginPageProfile, LoginPageOk,
    LoginFinalErrorPage,
    AccountsPage, InvestPage, LifeInsurancePage, AccountsPageSelenium,
)


class MyStablePageCondition(StablePageCondition):
    def __call__(self, driver):
        self._purge()

        source = driver.page_source.encode('utf-8')
        # wtf, this iframe attribute seem to change regularly
        source = re.sub(br' cd_frame_id_="\w+"', b'', source)

        hashed = hashlib.md5(source).hexdigest()
        now = time.time()
        page_id = driver.find_element_by_xpath('/*').id

        if page_id not in self.elements or self.elements[page_id][1] != hashed:
            self.elements[page_id] = (now, hashed)
            return False
        elif now - self.elements[page_id][0] < self.waiting:
            return False
        return True



class OptionsWithCookies(Options):
    # boursedirect uses another site (ulteo) to perform auth, 3rd party cookies are required

    def to_capabilities(self):
        caps = super(OptionsWithCookies, self).to_capabilities()
        caps[self.KEY].setdefault('prefs', {}).update({
            "profile": {
                "block_third_party_cookies": False,
            }
        })
        return caps


class BoursedirectBrowserSelenium(SeleniumBrowser):
    BASEURL = 'https://www.boursedirect.fr'

    HEADLESS = True
    DRIVER = webdriver.Chrome

    login1 = URL(r'/frmIdentif.php', LoginPage1)
    login_otp = URL(r'/frmIdentif.php', LoginPageOtp)
    login_profile = URL(r'/frmIdentif.php', LoginPageProfile)
    login_ok = URL(r'/frmIdentif.php', LoginPageOk)
    login_final_error = URL(r'/frmIdentif.php', LoginFinalErrorPage)
    login_final = URL(r'/frmIdentif.php', FinalLoginPage)

    accounts = URL(r'/priv/compte.php', AccountsPageSelenium)

    def __init__(self, config, *args, **kwargs):
        super(BoursedirectBrowserSelenium, self).__init__(*args, **kwargs)

        self.config = config
        self.username = config['login'].get()
        self.password = self.config['password'].get()

        logging.getLogger('selenium').setLevel(logging.ERROR)

    def _build_options(self):
        return OptionsWithCookies()

    def dump_state(self):
        ret = {
            'url': self.url,
            'cookies': {},
            'storage': {},
        }

        # selenium cannot retrieve all cookies/storage. it can only retrieve
        # them for the current domain. so we have to go to each domain in order
        # to get its cookies/storage
        urls = [
            'https://ult-inwebo.com/webapp/js/helium.min.js',
            'https://www.boursedirect.fr/streaming/inwebo/inwebo-mega.js',
        ]

        for url in urls:
            self.location(url)

            for i in range(10):
                try:
                    ret['cookies'][url] = [cookie.copy() for cookie in self.driver.get_cookies()]
                    ret['storage'][url] = self.get_storage()
                except WebDriverException as e:
                    # not only this selenium shit has no way to make sure a request is finished
                    # but it also spits useless exceptions in your face from time to time!
                    if 'unknown command' in e.msg:
                        time.sleep(1)
                        continue
                    raise
                else:
                    break
        return ret

    def load_state(self, state):
        if 'url' not in state or 'cookies' not in state:
            return

        # cookies/storage injection works same as loading, see dump_state
        for url, cookies in state['cookies'].items():
            self.location(url)

            for cookie in cookies:
                self.driver.add_cookie(cookie)

            if url in state['storage']:
                self.update_storage(state['storage'][url])

        self.accounts.go()

    @retry(TimeoutException, tries=2)
    def do_login(self):
        if self.page and self.page.logged:
            return

        if not self.login_otp.is_here():
            self.login1.go()
            self.wait_until(AnyCondition(
                IsHereCondition(self.login1),
                IsHereCondition(self.login_final),
                IsHereCondition(self.login_otp),
                IsHereCondition(self.login_profile),
            ))

        if self.login1.is_here():
            self.page.login(self.username)
            self.wait_until_is_here(self.login_otp)

        if self.login_otp.is_here():
            self.wait_until(MyStablePageCondition(3))
            if self.config['otp'].get():
                self.page.post_otp(self.config['otp'].get())
                self.wait_until_is_here(self.login_profile)
            else:
                raise BrowserQuestion(Value('otp', label='Entrez le code reçu par SMS'))

        if self.login_profile.is_here():
            self.wait_until(MyStablePageCondition(3))
            self.page.create_profile('weboob3', self.password)
            self.wait_until_is_here(self.login_ok)

        if self.login_ok.is_here():
            self.page.go_next()
            self.wait_until_is_here(self.login_final)

        if self.login_final.is_here():
            self.wait_until(MyStablePageCondition(3))
            self.page.login(self.username, self.password)
            self.wait_until(AnyCondition(
                IsHereCondition(self.login_final_error),
                IsHereCondition(self.accounts),
            ))
            if self.login_final_error.is_here():
                self.page.check_error()
            return

        if self.page and self.page.logged:
            return

        assert False, 'should not reach this'


class BoursedirectBrowser(SubSeleniumMixin, StatesMixin, PagesBrowser):
    BASEURL = 'https://www.boursedirect.fr'
    SELENIUM_BROWSER = BoursedirectBrowserSelenium

    accounts = URL(r'/priv/compte.php',
                   r'/priv/compte.php\?nc=(?P<nc>\d+)',
                   AccountsPage)
    pre_invests = URL(r'/priv/portefeuille-TR.php\?nc=(?P<nc>\d+)')
    invests = URL(r'/streaming/compteTempsReelCK.php\?stream=0', InvestPage)
    lifeinsurance = URL(r'/priv/asVieSituationEncours.php',
                        r'/priv/encours.php\?nc=\d+&idUnique=[\dA-F-]+',
                        LifeInsurancePage)

    def __init__(self, config, *args, **kwargs):
        super(BoursedirectBrowser, self).__init__(*args, **kwargs)
        self.config = config

    def dump_state(self):
        ret = super(BoursedirectBrowser, self).dump_state()
        return {'json': json.dumps(ret)}

    def load_state(self, state):
        if 'json' not in state:
            return
        state = json.loads(state['json'])

        return super(BoursedirectBrowser, self).load_state(state)

    @need_login
    def iter_accounts(self):
        self.accounts.go()
        for account in self.page.iter_accounts():
            self.accounts.go(nc=account._select)
            self.page.fill_account(obj=account)
            yield account

        self.lifeinsurance.go()
        if self.page.has_account():
            yield self.page.get_account()

    @need_login
    def iter_investment(self, account):
        if account.type == account.TYPE_LIFE_INSURANCE:
            self.lifeinsurance.go()
            for inv in self.page.iter_investment():
                yield inv
        else:
            self.pre_invests.go(nc=account._select)
            self.invests.go()

            for inv in self.page.iter_investment():
                yield inv
            yield self.page.get_liquidity()

    @need_login
    def iter_history(self, account):
        if account.type != account.TYPE_LIFE_INSURANCE:
            raise NotImplementedError()
        self.lifeinsurance.go()

        return sorted_transactions(self.page.iter_history())
