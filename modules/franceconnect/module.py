# Copyright(C) 2012-2020 Powens
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

from woob.capabilities.bill import CapDocument
from woob.tools.backend import Module

from .browser import FranceConnectBrowser


__all__ = ["FranceConnectModule"]


class FranceConnectModule(Module, CapDocument):
    NAME = "franceconnect"
    DESCRIPTION = "France Connect website"
    MAINTAINER = "Florian Duguet"
    EMAIL = "florian.duguet@budget-insight.com"
    LICENSE = "LGPLv3+"
    VERSION = "3.7"

    BROWSER = FranceConnectBrowser
