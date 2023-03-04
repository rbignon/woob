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
from urllib3.util.ssl_ import create_urllib3_context


__all__ = ['HTTPAdapter', 'LowSecHTTPAdapter']


class HTTPAdapter(requests.adapters.HTTPAdapter):
    """
    Custom Adapter class with extra features.

    :param proxy_headers: headers to send to proxy (if any)
    :type proxy_headers: dict
    """
    def __init__(self, *args, **kwargs):
        self._proxy_headers = kwargs.pop('proxy_headers', {})
        super().__init__(*args, **kwargs)

    def add_proxy_header(self, key, value):
        self._proxy_headers[key] = value

    def update_proxy_headers(self, headers):
        self._proxy_headers.update(headers)

    def proxy_headers(self, proxy):
        headers = super().proxy_headers(proxy)
        headers.update(self._proxy_headers)
        return headers


class LowSecHTTPAdapter(HTTPAdapter):
    """
    Adapter to use with low security HTTP servers.

    Some websites uses small DH keys, which is deemed insecure by OpenSSL's
    default config.  we have to lower its expectations so it accepts the
    certificate.

    See https://www.ssllabs.com/ssltest/analyze.html?d=www.ibps.bpaura.banquepopulaire.fr
    for the exhaustive list of defects they are too incompetent to fix
    """

    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context(ciphers="DEFAULT:@SECLEVEL=1")
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        context = create_urllib3_context(ciphers="DEFAULT:@SECLEVEL=1")
        kwargs['ssl_context'] = context
        return super().proxy_manager_for(*args, **kwargs)
