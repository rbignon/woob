# Copyright(C) 2010-2023  Romain Bignon
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

import os
import sys


if sys.platform == 'win32' \
        or not sys.stdout.isatty() \
        or os.getenv('NO_COLOR') is not None \
        or os.getenv('ANSI_COLORS_DISABLED') is not None:
    #workaround to disable bold
    BOLD   = ''
    NC     = ''         # no color
else:
    BOLD   = '\x1b[1m'
    NC     = '\x1b[0m'


try:
    from termcolor import colored
except ImportError:
    def colored(s, color=None, on_color=None, attrs=None):
        if os.getenv('ANSI_COLORS_DISABLED') is None \
                and os.getenv('NO_COLOR') is None \
                and attrs is not None and 'bold' in attrs:
            return '%s%s%s' % (BOLD, s, NC)
        else:
            return s


__all__ = ['colored', 'NC', 'BOLD']
