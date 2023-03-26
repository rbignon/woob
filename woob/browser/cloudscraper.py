# Copyright(C) 2023      Romain Bignon
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
"""
This module provides tools to bypass cloudflare websites with your browser.

To use it, add :class:`CloudScraperMixin` as a mixin of your browser class.
"""

try:
    from cloudscraper import CloudScraper
except ImportError as exc:
    raise ImportError('Please install cloudscraper') from exc


__all__ = ['CloudScraperSession', 'CloudScraperMixin']


class CloudScraperSession(CloudScraper):
    def send(self, *args, **kwargs):
        callback = kwargs.pop('callback', lambda future, response: response)
        is_async = kwargs.pop('is_async', False)

        if is_async:
            raise ValueError('Async requests are not supported')

        resp = super().send(*args, **kwargs)

        return callback(self, resp)


class CloudScraperMixin:
    def _create_session(self):
        return CloudScraperSession()

    def _setup_session(self, profile):
        session = self._create_session()

        session.hooks['response'].append(self.set_normalized_url)
        if self.responses_dirname is not None:
            session.hooks['response'].append(self.save_response)

        self.session = session
