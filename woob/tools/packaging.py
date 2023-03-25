# Copyright(C) 2023 Romain Bignon
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


from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.requirements import Requirement, InvalidRequirement


__all__ = ['parse_requirements']


def parse_requirements(path: str | Path) -> dict[str, SpecifierSet]:
    requirements = OrderedDict()

    try:
        with open(path, 'r', encoding='utf-8') as fp:
            for line in fp.readlines():
                try:
                    r = Requirement(line.strip())
                except InvalidRequirement:
                    # ignore blank lines or comments, but we also don't
                    # want to crash if requirements.txt contains incorrect
                    # lines. So use only this catch-all.
                    continue
                else:
                    requirements[r.name] = r.specifier
    except FileNotFoundError:
        # Assume this works with any version of woob.
        return {}

    return requirements
