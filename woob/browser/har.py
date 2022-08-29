# Copyright(C) 2012-2022 woob project
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


import base64
import io
import os
from datetime import datetime
from threading import Lock
from urllib.parse import urlparse, parse_qsl

from woob.tools.json import json
from woob.tools.log import getLogger
from woob import __version__ as woob_version

__all__ = ['HARManager']


class HARManager:
    def __init__(self, responses_dirname, logger):
        self.har_path = os.path.join(responses_dirname, 'bundle.har')
        self.responses_lock = Lock()
        self.logger = getLogger('har', logger)

        self.bundle = None

    def _build_har_bundle(self, started_datetime):
        self.bundle = {
            'log': {
                'version': '1.2',
                'creator': {
                    'name': 'woob',
                    'version': woob_version,
                },
                'browser': {
                    'name': 'woob',
                    'version': woob_version,
                },
                # there are no pages, but we need that to please firefox
                'pages': [{
                    'id': 'fake_page',
                    'pageTimings': {},
                    # and chromium wants some of it too
                    'startedDateTime': started_datetime,
                }],
                # don't put additional data after this list, to have a fixed-size suffix after it
                # so we can add more entries without rewriting the whole file.
                'entries': [],
            },
        }

    @staticmethod
    def _build_har_request(request, http_version):
        request_entry = {
            'method': request.method,
            'url': request.url,
            'httpVersion': http_version,
            'headers': [
                {
                    'name': k,
                    'value': v,
                }
                for k, v in request.headers.items()
            ],
            'queryString': [
                {
                    'name': key,
                    'value': value,
                }
                for key, value in parse_qsl(
                    urlparse(request.url).query,
                    keep_blank_values=True,
                )
            ],
            'cookies': [
                {
                    'name': k,
                    'value': v,
                }
                for k, v in request._cookies.items()
            ],
            # for chromium
            'bodySize': -1,
            'headersSize': -1,
        }

        if request.body is not None:
            request_entry['postData'] = {
                'mimeType': request.headers.get('Content-Type', ''),
                'params': [],
            }
            if isinstance(request.body, str):
                request_entry['postData']['text'] = request.body
            else:
                # HAR format has no proper way to encode posted binary data!
                request_entry['postData']['text'] = request.body.decode('latin-1')
                # add a non-standard key to indicate how should "text" be decoded.
                request_entry['postData']['x-binary'] = True

            if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
                request_entry['postData']['params'] = [
                    {
                        "name": key,
                        "value": value,
                    } for key, value in parse_qsl(request.body)
                ]

        return request_entry

    @staticmethod
    def _build_har_response(response):
        response_entry = {
            'status': response.status_code,
            'statusText': response.reason,
            'httpVersion': 'HTTP/%.1f' % (response.raw.version / 10.),
            'headers': [
                {
                    'name': k,
                    'value': v,
                }
                for k, v in response.headers.items()
            ],
            'content': {
                'mimeType': response.headers.get('Content-Type', ''),
                'size': len(response.content),
                # systematically use base64 to avoid more content alteration
                # than there already is...
                'encoding': "base64",
                'text': base64.b64encode(response.content).decode('ascii'),
            },
            'cookies': [
                {
                    'name': k,
                    'value': v,
                }
                for k, v in response.cookies.items()
            ],
            'redirectURL': response.headers.get('location', ''),
            # for chromium
            'bodySize': -1,
            'headersSize': -1,
        }
        return response_entry

    @staticmethod
    def _build_empty_har_response(*args):
        # called when we get a timeout
        return {
            'status': 0,
            'statusText': '',
            'httpVersion': '',
            'headers': [],
            'content': {},
            'cookies': [],
            'redirectURL': '',
            # for chromium
            'bodySize': -1,
            'headersSize': -1,
        }

    def _build_har_entry(self, slug, request, response=None, time=''):
        # check if response is not None and not if response
        # because a response with a status_code >= 400 is falsy
        if response is not None:
            started_datetime = (datetime.now() - response.elapsed).isoformat()
            time = int(response.elapsed.total_seconds() * 1000)
            http_version = 'HTTP/%.1f' % (response.raw.version / 10.)
            build_response = self._build_har_response
        else:
            started_datetime = datetime.now().isoformat()
            build_response = self._build_empty_har_response
            http_version = ''

        if not self.bundle:
            self._build_har_bundle(started_datetime)

        har_entry = {
            '$anchor': slug,
            'startedDateTime': started_datetime,
            'pageref': 'fake_page',
            'time': time,
            'request': self._build_har_request(request, http_version),
            'response': build_response(response),
            'timings': {  # please chromium
                'send': -1,
                'wait': -1,
                'receive': -1,
            },
            'cache': {},
        }
        return har_entry

    def _save_har_entry(self, har_entry):
        self.bundle['log']['entries'].append(har_entry)

        if not os.path.isfile(self.har_path):
            with open(self.har_path, 'w') as fd:
                json.dump(self.bundle, fd, separators=(',', ':'))
        else:
            # hack to avoid rewriting the whole file: entries are last in the JSON file
            # we need to seek at the right place and write the new entry.
            # this will unfortunately overwrite closings.
            suffix = "]}}"
            with open(self.har_path, 'r+') as fd:
                # can't seek with a negative value...
                fd.seek(0, io.SEEK_END)
                after_entry_pos = fd.tell() - len(suffix)
                fd.seek(after_entry_pos)

                if fd.read(len(suffix)) != suffix:
                    self.logger.warning('HAR file does not end with the expected pattern')
                else:
                    fd.seek(after_entry_pos)
                    fd.write(',')  # there should have been at least one entry
                    json.dump(har_entry, fd, separators=(',', ':'))
                    fd.write(suffix)

    def save_response(self, slug, response):
        request = response.request
        har_entry = self._build_har_entry(slug, request, response=response)

        with self.responses_lock:
            self._save_har_entry(har_entry)

    def save_request_only(self, slug, request, time):
        har_entry = self._build_har_entry(slug, request, time=time)
        with self.responses_lock:
            self._save_har_entry(har_entry)
