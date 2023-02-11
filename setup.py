#! /usr/bin/env python3

# Copyright(C) 2010-2021 Christophe Benz
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

import glob
import os
import sys

from setuptools import find_packages, setup



def install_woob():
    packages = set(find_packages(exclude=['modules', 'modules.*']))

    data_files = [
        ('share/man/man1', glob.glob('man/*')),
    ]

    requirements = [
        'lxml',
        'requests >= 2.0.0',
        'python-dateutil',
        'PyYAML',
        'html2text >= 3.200',
        'unidecode',
        'Pillow',
        'Babel',
        'packaging ~= 23.0',
    ]

    try:
        if sys.argv[1] == 'requirements':
            print('\n'.join(requirements))
            sys.exit(0)
    except IndexError:
        pass

    setup(
        packages=packages,
        data_files=data_files,
    )


if os.getenv('WOOB_SETUP'):
    args = os.getenv('WOOB_SETUP').split()
else:
    args = sys.argv[1:]

sys.argv = [sys.argv[0]] + args

install_woob()
