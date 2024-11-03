from woob.capabilities.bank import (
    CapBank, Account, Transaction,
    AccountNotFound
)
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import Value, ValueTransient, ValueBackendPassword
from woob.browser.browsers import Browser

from woob.browser.mfa import TwoFactorBrowser

from woob.browser.browsers import need_login
from woob.browser.url import URL
from woob.capabilities.base import find_object

from .browser import GreenGotBrowser

import json
import re




__all__ = ['GreenGotModule']


class GreenGotModule(Module, CapBank):
    NAME = 'greengot'      
    DESCRIPTION = 'Module bancaire pour Greengot'
    MAINTAINER = 'Pierre BOULC\'H'
    VERSION = '1.0'
    CONFIG = BackendConfig(
        Value('login', label='Email', regexp='.+'),
        ValueTransient('smscode'),
        ValueTransient('emailcode')
    )
    BROWSER = GreenGotBrowser


    def create_default_browser(self):
        return self.create_browser(self.config, self.config['login'].get())
    
    def iter_accounts(self):
        return self.browser.iter_accounts()
    
    def iter_history(self, account):
        return self.browser.iter_history(account)


