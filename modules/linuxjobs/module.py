# Copyright(C) 2016      François Revol
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


from woob.capabilities.job import CapJob
from woob.tools.backend import Module

from .browser import LinuxJobsBrowser


__all__ = ["LinuxJobsModule"]


class LinuxJobsModule(Module, CapJob):
    NAME = "linuxjobs"
    DESCRIPTION = "linuxjobs website"
    MAINTAINER = "François Revol"
    EMAIL = "revol@free.fr"
    LICENSE = "AGPLv3+"
    VERSION = "3.7"

    BROWSER = LinuxJobsBrowser

    def advanced_search_job(self):
        """
         Iter results of an advanced search

        :rtype: iter[:class:`BaseJobAdvert`]
        """
        raise NotImplementedError()

    def get_job_advert(self, _id, advert=None):
        """
        Get an announce from an ID.

        :param _id: id of the advert
        :type _id: str
        :param advert: the advert
        :type advert: BaseJobAdvert
        :rtype: :class:`BaseJobAdvert` or None if not found.
        """
        return self.browser.get_job_advert(_id, advert)

    def search_job(self, pattern=None):
        """
        Iter results of a search on a pattern.

        :param pattern: pattern to search on
        :type pattern: str
        :rtype: iter[:class:`BaseJobAdvert`]
        """
        yield from self.browser.search_job(pattern)
