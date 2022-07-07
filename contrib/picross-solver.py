#!/usr/bin/env python3

# flake8: compatible

# Copyright(C) 2022      Thomas Touhey <thomas@touhey.fr>
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

import argparse
from os import linesep

from woob.capabilities.picross import (
    PicrossNotFound, PicrossSolution, PicrossSolutionKind, PicrossSolvedStatus,
)
from woob.core.woob import Woob


class PicrossSolver:
    @staticmethod
    def combinations(fmt, length):
        """Yields combinations of the following format and length.

        The format here is expected to be a tuple of the given lengths,
        e.g. (3, 2), and the length is expected to be the full length
        in squares of the lines to generate.

        For example, if the combinations is (1, 2) and the length is 5,
        the following lines will be yielded:

            'x xx '
            'x  xx'
            ' x xx'

        Note that the order is not guaranteed.
        """

        min_length = sum(fmt) + len(fmt) - 1
        if min_length > length:
            return []

        def combinations_recur(fmt, spaces):
            if not fmt:
                yield ' ' * spaces
                return

            fst, *rest = fmt
            for current_spaces in range(0, spaces + 1):
                for combination in combinations_recur(
                    rest,
                    spaces - current_spaces,
                ):
                    yield (
                        ' ' * current_spaces + 'x' * fst
                        + (' ' if rest else '') + combination
                    )

        return list(combinations_recur(fmt, length - min_length))

    @staticmethod
    def precise(combinations, current_row):
        """Determine possible combinations out of the current row.

        Combinations are a list of possible rows previously generated
        by the `combinations` static method. Using `current_row` as the
        current state of the row, this function removes combinations
        that are incompatible with the current state of the row.
        """

        for i in range(len(combinations) - 1, -1, -1):
            incompatible = False
            for cc, cx in zip(combinations[i], current_row):
                if cx != '?' and cx != cc:
                    incompatible = True
                    break

            if incompatible:
                del combinations[i]

        return combinations

    @staticmethod
    def intersection(combinations):
        """Precise a given line with unknown placements.

        For example, if the combinations is (1, 2) and the current row
        is 'x????', this function will return 'x ?x?', since the second
        character is necessary blank and the penultimate character is
        necessarily an 'x'.
        """

        def intersection_inner(combinations):
            for s in zip(*combinations):
                if all(c == s[0] for c in s[1:]):
                    yield s[0]
                else:
                    yield '?'

        return ''.join(intersection_inner(combinations))

    def solve(self, puzzle):
        """Return a solution for a given picross puzzle.

        :rtype: PicrossSolution
        """

        w, h = len(puzzle.columns), len(puzzle.lines)
        ye = puzzle.columns
        xe = puzzle.lines

        yc = [self.combinations(fmt, h) for fmt in ye]
        xc = [self.combinations(fmt, w) for fmt in xe]

        current = [self.intersection(c) for c in xc]

        while True:
            no_unknown = True

            for x in range(w):
                if len(yc) == 1:
                    continue

                current_column = ''.join(s[x] for s in current)
                yc[x] = self.precise(yc[x], current_column)
                new_column = self.intersection(yc[x])
                if '?' in new_column:
                    no_unknown = False

                for y, c in enumerate(new_column):
                    s = current[y]
                    current[y] = s[:x] + c + s[x + 1:]

            for y in range(h):
                if len(xc) == 1:
                    continue

                current_row = current[y]
                xc[y] = self.precise(xc[y], current_row)
                new_row = self.intersection(xc[y])
                if '?' in new_row:
                    no_unknown = False

                current[y] = new_row

            if no_unknown:
                break

        # Make the solution out of the current state.
        solution = PicrossSolution()
        solution.kind = PicrossSolutionKind.PLACEMENTS
        solution.lines = current

        return solution


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Solve some picrosses using Woob!',
    )
    parser.add_argument('-b', dest='backend', required=True)
    subcommands = parser.add_subparsers(dest='command', required=True)

    list_unsolved = subcommands.add_parser(
        'list-unsolved',
        description='List unsolved picrosses.',
    )
    list_unsolved.set_defaults(func=list_unsolved)

    solve = subcommands.add_parser(
        'solve',
        description='Solve a given picross',
    )
    solve.add_argument('id', help='Identifier of the picross to solve.')
    solve.set_defaults(func=solve)

    parsed_args = parser.parse_args()

    woob = None
    try:
        woob = Woob()
        woob.load_backends(names=(parsed_args.backend,))

        try:
            backend = woob.get_backend(parsed_args.backend)
        except KeyError:
            print(f'No backend with the name {parsed_args.backend!r}.')
            exit()

        if parsed_args.command == 'list-unsolved':
            is_first = True
            has_stopped_naturally = False
            for i, picross in enumerate(backend.iter_picross_puzzles(
                PicrossSolvedStatus.UNSOLVED,
            )):
                if is_first:
                    print('Available picrosses:', end=linesep * 2)
                    is_first = False

                print(f'{picross.id} - {picross.name} ({picross.variant})')

                if i >= 4:
                    break
            else:
                has_stopped_naturally = True

            if is_first:
                print('No unsolved picross available. Better luck next time!')
            elif not has_stopped_naturally:
                print(linesep + '... and more!')
        elif parsed_args.command == 'solve':
            try:
                picross = backend.get_picross_puzzle(parsed_args.id)
            except PicrossNotFound:
                print('Picross not found.')
            else:
                solver = PicrossSolver()
                solution = solver.solve(picross)

                print('Found the following solution:', end=linesep * 2)

                for line in solution.lines:
                    print(' '.join(line))

                print('')  # Print an empty line in case of error here.
                backend.submit_picross_puzzle_solution(picross, solution)
                print('Submitted the solution.')
        else:
            print(f'Unknown command {parsed_args.command!r}!')
    finally:
        if woob is not None:
            woob.deinit()
