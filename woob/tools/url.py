# Copyright(C) 2022 Budget Insight
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

# flake8: compatible

import typing as t
from urllib.parse import parse_qsl, urlencode, urlparse

from woob.tools.misc import NO_DEFAULT, NoDefaultType

__all__ = [
    'get_url_fragment_param', 'get_url_fragment_params',
    'get_url_param', 'get_url_params', 'get_url_with_params',
]


def get_url_param(
    url: str, name: str, *,
    default: t.Union[t.Optional[str], NoDefaultType] = NO_DEFAULT,
) -> t.Optional[str]:
    """Get a specific query parameter from an URL.

    :param url: The URL to get the parameter from.
    :param name: The name of the query parameter to get.
    :param default: The default value, as a string or None.
                    Should not be set if the function should raise an exception
                    in cases where no value could be obtained using this URL
                    and name.
    """
    parsed_url = urlparse(url)
    params = dict(parse_qsl(parsed_url.query, keep_blank_values=True))
    if name not in params:
        if default is NO_DEFAULT:
            raise ValueError(
                f'URL {url!r} has no query parameter named {name!r}.',
            )

        return default

    return params[name]


def get_url_fragment_param(
    url: str, name: str, *,
    default: t.Union[t.Optional[str], NoDefaultType] = NO_DEFAULT,
) -> t.Optional[str]:
    """Get a specific fragment parameter from an URL.

    Note that this function is only for cases where the fragment is encoded
    the same way as a query string, e.g. 'https://example.org/#a=b&c=d'.

    :param url: The URL to get the fragment parameter from.
    :param name: The name of the fragment parameter to get.
    :param default: The default value, as a string or None.
                    Should not be set if the function should raise an exception
                    in cases where no value could be obtained using this URL
                    and name.
    """
    parsed_url = urlparse(url)
    params = dict(parse_qsl(parsed_url.fragment, keep_blank_values=True))
    if name not in params:
        if default is NO_DEFAULT:
            raise ValueError(
                f'URL {url!r} has no fragment parameter named {name!r}.',
            )

        return default

    return params[name]


def get_url_params(url: str) -> t.Dict[str, str]:
    """Get query parameters from an URL.

    :param url: The URL to get the parameters from.
    """
    parsed_url = urlparse(url)
    return dict(parse_qsl(parsed_url.query, keep_blank_values=True))


def get_url_fragment_params(url: str) -> t.Dict[str, str]:
    """Get fragment parameters from an URL.

    Note that this function is only for cases where the fragment is encoded
    the same way as a query string, e.g. 'https://example.org/#a=b&c=d'.

    :param url: The URL to get the parameters from.
    """
    parsed_url = urlparse(url)
    return dict(parse_qsl(parsed_url.fragment, keep_blank_values=True))


def get_url_with_params(url: str, **kwargs: t.Optional[str]) -> str:
    """Get an URL with additional or without some query parameters.

    :param url: The URL to modify.
    """
    parsed_url = urlparse(url)
    params = dict(parse_qsl(parsed_url.query, keep_blank_values=True))

    for key, value in kwargs.items():
        if value is None:
            if key in params:
                del params[key]
        else:
            params[key] = str(value)

    return parsed_url._replace(
        query=urlencode(params, doseq=True),
    ).geturl()
