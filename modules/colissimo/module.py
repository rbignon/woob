# Copyright(C) 2013 Florent Fourcot
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

from woob.capabilities.parcel import CapParcel, ParcelNotFound
from woob.tools.backend import Module

from .browser import ColissimoBrowser


__all__ = ["ColissimoModule"]


class ColissimoModule(Module, CapParcel):
    NAME = "colissimo"
    DESCRIPTION = "Colissimo parcel tracking website"
    MAINTAINER = "Florent Fourcot"
    EMAIL = "weboob@flo.fourcot.fr"
    VERSION = "3.7"
    LICENSE = "AGPLv3+"

    BROWSER = ColissimoBrowser

    def get_parcel_tracking(self, _id):
        # 13 is the magic length of colissimo tracking ids
        if len(_id) != 13:
            raise ParcelNotFound("Colissimo ID's must have 13 print character")

        return self.browser.get_tracking_info(_id)
