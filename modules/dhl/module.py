# Copyright(C) 2015      Matthieu Weber
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

from .browser import DeutschePostDHLBrowser, DHLExpressBrowser


__all__ = ["DHLModule"]


class DHLModule(Module, CapParcel):
    NAME = "dhl"
    DESCRIPTION = "DHL website"
    MAINTAINER = "Matthieu Weber"
    EMAIL = "mweber+weboob@free.fr"
    LICENSE = "AGPLv3+"
    VERSION = "3.7"

    def get_parcel_tracking(self, id):
        """
        Get information abouut a parcel.

        :param id: ID of the parcel
        :type id: :class:`str`
        :rtype: :class:`Parcel`
        :raises: :class:`ParcelNotFound`
        """
        self._browser = None
        if len(id) == 10 or len(id) == 20:
            self.BROWSER = DHLExpressBrowser
        elif len(id) == 12 or len(id) == 13 or len(id) == 16:
            self.BROWSER = DeutschePostDHLBrowser
        else:
            raise ParcelNotFound("Wrong length for ID: %s" % id)

        return self.browser.get_tracking_info(id)
