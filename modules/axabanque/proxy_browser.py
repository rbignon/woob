# -*- coding: utf-8 -*-

# Copyright(C) 2022 Damien Ramelet
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

# flake8: compatible

from woob.browser.switch import SwitchingBrowser

from .browser import AXABanqueBrowser, AXABourseBrowser, AXAAssuranceBrowser


class ProxyBrowser(SwitchingBrowser):
    BROWSERS = {
        'main': AXABanqueBrowser,
        'bourse': AXABourseBrowser,
        'insurance': AXAAssuranceBrowser,
    }

    KEEP_SESSION = True
    KEEP_ATTRS = (
        'axa_assurance_base_url', 'axa_assurance_url_path', 'is_coming_from_axa_bank',
    )
