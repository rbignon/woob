# Copyright(C) 2010-2013 Christophe Benz
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

from warnings import warn

from .bcall import CallErrors
from .woob import Woob, WoobBase

__all__ = ['CallErrors', 'Woob', 'WoobBase', 'Weboob', 'WebNip']


class WebNip(WoobBase):
    """Deprecated alias for the freestanding WoobBase application.

    .. deprecated:: 3.0
        Please use :mod:`woob.core.woob.WoobBase` instead.
    """

    def __init__(self, *args, **kwargs):
        warn(
            'WebNip is a deprecated alias and will be removed in Woob 4.0, '
            + 'use WoobBase from woob.core.woob.',
            DeprecationWarning,
            stacklevel=2,
        )

        super().__init__(*args, **kwargs)


class Weboob(Woob):
    """Deprecated alias for the hosted Woob application.

    .. deprecated:: 3.0
        Please use :mod:`woob.core.woob.Woob` instead.
    """

    def __init__(self, *args, **kwargs):
        warn(
            'Weboob is a deprecated alias and will be removed in Woob 4.0, '
            + 'use Woob from woob.core.woob.',
            DeprecationWarning,
            stacklevel=2,
        )

        super().__init__(*args, **kwargs)
