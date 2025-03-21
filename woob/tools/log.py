# Copyright(C) 2010-2011 Romain Bignon
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

import sys
from collections import defaultdict
from logging import Formatter, LoggerAdapter, addLevelName
from logging import getLogger as _getLogger


__all__ = ["getLogger", "createColoredFormatter", "settings"]


RESET_SEQ = "\033[0m"
COLOR_SEQ = "%s%%s" + RESET_SEQ

COLORS = {
    "DEBUG": COLOR_SEQ % "\033[0;36m",
    "INFO": COLOR_SEQ % "\033[32m",
    "WARNING": COLOR_SEQ % "\033[1;33m",
    "ERROR": COLOR_SEQ % "\033[1;31m",
    "CRITICAL": COLOR_SEQ % ("\033[1;33m\033[1;41m"),
    "DEBUG_FILTERS": COLOR_SEQ % "\033[0;35m",
}

DEBUG_FILTERS = 8
addLevelName(DEBUG_FILTERS, "DEBUG_FILTERS")


# Global settings f logger.
settings = defaultdict(lambda: None)


def getLogger(name, parent=None):
    if isinstance(parent, LoggerAdapter):
        klass = type(parent)
        extra = parent.extra
        parent = parent.logger
    else:
        klass = None
        extra = None

    if parent:
        name = parent.name + "." + name
    logger = _getLogger(name)
    logger.settings = settings

    if extra:
        logger = klass(logger, extra)
        logger.settings = settings
    return logger


class ColoredFormatter(Formatter):
    """
    Class written by airmind:
    https://stackoverflow.com/questions/384076/how-can-i-make-the-python-logging-output-to-be-colored
    """

    def format(self, record):
        levelname = record.levelname

        msg = super().format(record)
        if levelname in COLORS:
            msg = COLORS[levelname] % msg
        return msg


def createColoredFormatter(stream, format):
    if (sys.platform != "win32") and stream.isatty():
        return ColoredFormatter(format)
    else:
        return Formatter(format)


if __name__ == "__main__":
    for levelname, cs in COLORS.items():
        print(cs % levelname, end=" ")
