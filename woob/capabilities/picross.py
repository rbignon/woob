# flake8: compatible

# Copyright(C) 2022 Thomas Touhey <thomas@touhey.fr>
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

from woob.capabilities.base import (
    BaseObject, Capability, Enum, EnumField, Field, StringField, UserError,
)

__all__ = [
    'CapPicross', 'Picross', 'PicrossNotFound', 'PicrossSolution',
    'PicrossSolvedStatus',
]


class PicrossNotFound(UserError):
    """
    Raised when a picross puzzle is not found.
    """

    def __init__(self, msg='Picross not found'):
        super().__init__(msg)


class PicrossVariant(Enum):
    """
    The picross rules variant.

    BASIC is the most basic set of rules, with only one color and only
    lines and columns with numbers. It applies to both picrosses and nonograms.

    COLORED is a more advanced set of rules giving colors to numbers. It also
    sets color_lines and color_columns.
    """

    BASIC = 'basic'
    COLORED = 'colored'


class PicrossSolvedStatus(Enum):
    UNKNOWN = 'unknown'
    SOLVED = 'solved'
    UNSOLVED = 'unsolved'


class PicrossSolutionKind(Enum):
    """
    The picross solution kind.

    Both BASIC and COLORED can be solved using PLACEMENTS solutions; see
    PicrossSolution for more information.
    """

    PLACEMENTS = 'placements'


class Picross(BaseObject):
    """
    Picross puzzle representation.

    For example, take the following basic black and white puzzle:

                 1
             1 3 3 2

          3    X X X
        2 1  X X   X
          2    X X
          1      X
          1      X

    It is represented the following way:

        lines = [(3,), (2, 1), (2,), (1,), (1,)]
        columns = [(1,), (3,), (1, 3), (2,)]

    Note that empty lines and/or columns are either represented with an empty
    tuple or as (0,) depending on what is convenient for the module,
    e.g. the following pattern:


           1 1 1
           1 1 1

        3  X X X
        0
        3  X X X

    Is either represented the following way:

        lines = [(3,), (), (3,)]
        columns = [(1, 1), (1, 1), (1, 1)]

    Or the following way:

        lines = [(3,), (0,), (3,)]
        columns = [(1, 1), (1, 1), (1, 1)]

    Colored puzzles, on the other hand, associate colors to a puzzle by
    populating color_lines and color_columns. Since it is possible to
    distinguish groups by using the color, it does not require gaps between
    groups, which can just be stuck together.

    For example, take the following colored puzzle:

                        3G
                  2G 4G 2R 4G 2G

              3G      G  G  G
              5G   G  G  G  G  G
              5G   G  G  G  G  G
        1G 1R 1G      G  R  G
              1R         R

    It is represented the following way:

        lines = [(3,), (5,), (5,), (1, 1, 1), (1,)]
        columns = [(2,), (4,), (3, 2), (4,), (2,)]
        line_colors = [(G,), (G,), (G,), (G, R, G), (R,)]
        column_colors = [(G,), (G,), (G, R), (G,), (G,)]

    Where R = 0xFF0000 (i.e. 16711680) and G = 0x00FF00 (i.e. 65280), since
    color components are integers representing sRGB colors.
    """

    name = StringField('The friendly name of the picross puzzle, if available')
    variant = EnumField(
        'The rules variant for the picross',
        enum=PicrossVariant,
        default=PicrossVariant.BASIC,
    )
    solved_status = EnumField(
        'Whether the picross has been solved or not',
        enum=PicrossSolvedStatus,
        default=PicrossSolvedStatus.UNKNOWN,
    )
    lines = Field('List of line tuples', list)
    columns = Field('List of column tuples', list)

    color_lines = Field('List of colors given to groups on rows', list)
    color_columns = Field('List of colors given to groups on columns', list)


class PicrossSolution(BaseObject):
    """
    Picross puzzle solution representation.

    For example, take the following puzzle:

                 1
             1 3 3 2

          3    X X X
        2 1  X X   X
          2    X X
          1      X
          1      X

    The puzzle is represented line by line, as the following:

        lines = [' xxx', 'xx x', ' xx ', '  x ', '  x ']

    Note that if the solution is for a colored picross, it is possible
    to deduce the colors from the puzzle data and the solution placements,
    and colors do not need to be included in the solution.
    """

    kind = EnumField(
        'The solution kind to the picross solution.',
        enum=PicrossSolutionKind,
        default=PicrossSolutionKind.PLACEMENTS,
    )

    lines = Field('List of lines with x-es and spaces', list)


class CapPicross(Capability):
    """
    Capability for getting picross / nonogram puzzles and solving them.
    """

    can_submit_picross_puzzle_solution = False
    """
    Set to True in your module if it is possible to submit solutions
    under at least some circumstances (e.g. being logged in).
    """

    def iter_picross_puzzles(self, solved_status):
        """
        Iter available picross / nonogram puzzles.

        :rtype: iter[:class:`Picross`]
        """

        raise NotImplementedError()

    def get_picross_puzzle(self, puzzle_id):
        """
        Get a picross / nonogram puzzle from its ID.

        :param id: ID of the puzzle
        :type id: :class:`str`
        :rtype: :class:`Picross`
        :raises: :class:`PicrossNotFound`
        """

        raise NotImplementedError()

    def submit_picross_puzzle_solution(self, puzzle, solution):
        """
        Submit a picross / nonogram puzzle solution.

        :param puzzle: The puzzle as gathered by the module.
        :type puzzle: :class:`Picross`
        :param solution: The puzzle solution.
        :type solution: :class:`PicrossSolution`
        """

        raise NotImplementedError()
