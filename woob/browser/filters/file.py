# Copyright(C) 2023 Powens
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

import mimetypes
from os.path import splitext
from typing import Any

from woob.browser.filters.standard import CleanText, FormatError
from woob.capabilities.base import empty
from woob.tools.misc import NO_DEFAULT

from .base import debug

__all__ = ['MimeType', 'FileExtension']


class MimeType(CleanText):
    """
    A filter to determine the MIME Type (Multipurpose Internet Mail Extensions)
    of a file based on a given string, which can be a file path or a file name with an extension.

    :param default: The default MIME type to be returned when the file type is not recognized.
    :type default: Any, optional
    """
    @debug()
    def filter(self, txt: str) -> Any:
        """
        Get the MIME type from a file name or path.

        :param txt: The file name or path for which to determine the MIME type.
        :type txt: str
        :raises FormatError: If the MIME type is not recognized.

        >>> MimeType().filter('foo.pdf')
        'application/pdf'
        >>> MimeType().filter('path/foo/invoices.tar.gz')
        'application/x-tar'
        >>> MimeType(default='NAN').filter('foo.no')
        'NAN'
        """
        txt = super().filter(txt)

        if empty(txt):
            return self.default_or_raise(FormatError(f'Unable to parse {txt}'))
        # The 'mimetypes.guess_type()' function requires a valid
        # file name with an extension (file_name.extension)
        # to determine the MIME type. It may not handle inputs without a dot ('pdf'),
        # or with a dot but no name ('.pdf').
        if txt.startswith('.'):
            # .pdf
            txt = f'dummy_filename{txt}'
        if '.' not in txt:
            # pdf
            txt = f'dummy_filename.{txt}'

        mime_type, _ = mimetypes.guess_type(txt)
        if not mime_type:
            return self.default_or_raise(
                FormatError(f'MIME type not recognized for file: {txt}')
            )
        return mime_type


class FileExtension(CleanText):
    """
    A filter to extract the file extension from a given string representing
    a file name or a file path.

    :param default: The default extension to be returned when the file extension is not recognized.
    :type default: Any, optional
    :param validate_mime: Flag to indicate whether to validate the MIME type of the returned extension.
    :type validate_mime: bool, optional
    """

    def __init__(self, selector=None, validate_mime=False, default=NO_DEFAULT):
        super().__init__(selector, default=default)
        self.validate_mime = validate_mime

    @debug()
    def filter(self, txt: str) -> Any:
        """
        Get the file extension from a file name or path.

        :param txt: The file name or path for which to extract the file extension.
        :type txt: str
        :raises FormatError: If the file extension is not recognized.

        >>> FileExtension().filter('file.docx')
        'docx'
        >>> FileExtension().filter('path/to/file.tar.gz')
        'tar.gz'
        >>> FileExtension(default='NAN').filter('file_without_extension')
        'NAN'
        >>> FileExtension().filter('/home/user/Documents/report.pdf')
        'pdf'
        >>> FileExtension(default='UNKNOWN').filter('spreadsheet')
        'UNKNOWN'
        >>> FileExtension(default='UNKNOWN', validate_mime=True).filter('path/to/file.dfs')
        'UNKNOWN'
        >>> FileExtension(default='UNKNOWN', validate_mime=True).filter('file.jpg')
        'jpg'
        """
        txt = super().filter(txt)
        if empty(txt):
            return self.default_or_raise(FormatError(f'Unable to parse {txt}'))

        if len(txt.split('.')) > 2:
            extension = '.'.join(txt.split('.')[-2:])
        else:
            _, extension = splitext(txt)
            if not extension:
                return self.default_or_raise(FormatError(f'Extension not recognized: {txt}'))
            extension = extension.strip('.')

        if self.validate_mime:
            try:
                MimeType().filter(extension)
            except FormatError:
                return self.default_or_raise(FormatError(
                    f'MIME type not recognized for the extension {extension}')
                )
        return extension
