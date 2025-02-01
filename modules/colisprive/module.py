# -*- coding: utf-8 -*-

# Copyright(C) 2014 Florent Fourcot
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

from woob.capabilities.parcel import CapParcel
from woob.tools.backend import Module

from .browser import ColispriveBrowser


__all__ = ["ColispriveModule"]


class ColispriveModule(Module, CapParcel):
    NAME = "colisprive"
    DESCRIPTION = "Colisprive parcel tracking website"
    MAINTAINER = "Florent Fourcot"
    EMAIL = "weboob@flo.fourcot.fr"
    VERSION = "3.7"
    LICENSE = "AGPLv3+"

    BROWSER = ColispriveBrowser

    def get_parcel_tracking(self, _id):
        return self.browser.get_tracking_info(_id)
