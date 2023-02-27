# Copyright(C) 2019 Romain Bignon
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


import requests
import urllib3


__all__ = ['HTTPAdapter']


class HTTPAdapter(requests.adapters.HTTPAdapter):
    """
    Custom Adapter class with extra features.

    :param proxy_headers: headers to send to proxy (if any)
    :type proxy_headers: dict
    :param ciphers: ciphers chain to use in TLS connection
    :type ciphers: str
    """
    def __init__(self, *args, **kwargs):
        self._proxy_headers = kwargs.pop('proxy_headers', {})
        ciphers = kwargs.pop('ciphers', None)
        self._ssl_context = kwargs.pop('ssl_context', None)

        if ciphers:
            if not self._ssl_context:
                self._ssl_context = urllib3.util.ssl_.create_urllib3_context()
            self._ssl_context.set_ciphers(ciphers)

        super().__init__(*args, **kwargs)

    def add_proxy_header(self, key, value):
        self._proxy_headers[key] = value

    def update_proxy_headers(self, headers):
        self._proxy_headers.update(headers)

    def proxy_headers(self, proxy):
        headers = super().proxy_headers(proxy)
        headers.update(self._proxy_headers)
        return headers

    def init_poolmanager(self, *args, **kwargs):
        kwargs['ssl_context'] = self._ssl_context
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs['ssl_context'] = self._ssl_context
        return super().proxy_manager_for(*args, **kwargs)
