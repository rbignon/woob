# Copyright(C) 2024      Ludovic LANGE
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

from typing import Iterable, List

from woob.capabilities.base import (
    BaseObject, find_object
)
from woob.capabilities.bank import Account

from woob_modules.cmso.module import CmsoModule
from woob.tools.backend import BackendConfig

from woob.tools.value import Value, ValueBackendPassword, ValueTransient

from .browser import CCFParBrowser, CCFProBrowser


__all__ = ['CCFModule']


class CCFModule(CmsoModule):
    NAME = 'ccf'
    DESCRIPTION = 'CCF (ex- HSBC France)'
    MAINTAINER = 'Ludovic LANGE'
    EMAIL = 'llange@users.noreply.github.com'
    LICENSE = 'LGPLv3+'
    DEPENDENCIES = ('cmso',)
    AVAILABLE_BROWSERS = {'par': CCFParBrowser, 'pro': CCFProBrowser}
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', regexp=r'^\d{9}$', masked=False),
        ValueBackendPassword('password', label='Mot de passe', regexp=r'^\d{8}$'),
        ValueBackendPassword('security_code', label=u'Code de sécurité', regexp=r'^\d{5}$'),
        ValueTransient('code'),
        ValueTransient('request_information'),
        Value(
            'website',
            label='Type de compte',
            default='par',
            choices={
                'par': 'Particuliers',
                'pro': 'Professionnels',
            }
        )
    )
