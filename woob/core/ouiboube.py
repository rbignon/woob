# Copyright(C) 2010-2021 Romain Bignon
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

"""
.. deprecated:: 3.0
   Please use :mod:`woob.core.woob` instead.
"""

import warnings
from .woob import WoobBase, Woob, VersionsMismatchError  # noqa

__all__ = ["WoobBase", "Woob", "VersionsMismatchError", "Weboob", "WebNip"]

warnings.warn(
    'Please use woob.core.woob instead.',
    DeprecationWarning,
    stacklevel=2,
)

WebNip = WoobBase
Weboob = Woob
