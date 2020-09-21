#!/usr/bin/env python3

from argparse import ArgumentParser, FileType
from base64 import b64decode
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlparse


def write_request(entry, fd):
    entry = entry['request']

    # we should put the path, but since requests does not output the Host header
    # we would not know what was the host
    fd.write(f"{entry['method']} {entry['url']} {entry['httpVersion']}\n".encode())

    for header in entry['headers']:
        fd.write(f"{header['name']}: {header['value']}\n".encode())

    fd.write(b'\n')

    if 'postData' in entry:
        if entry['postData'].get('x-binary'):
            # non-standard key emitted by weboob
            body = entry['postData']['text'].encode('latin-1')
        else:
            body = entry['postData']['text'].encode()
        fd.write(body)


def write_response(entry, fd):
    entry = entry['response']
    fd.write(f"{entry['httpVersion']} {entry['status']} {entry['statusText']}\n")
    for header in entry['headers']:
        fd.write(f"{header['name']}: {header['value']}\n")


def write_body(entry, fd):
    entry = entry['response']
    if entry['content'].get('encoding') == 'base64':
        data = b64decode(entry['content']['text'])
    else:
        data = entry['content']['text'].encode('utf-8')
    fd.write(data)


def guess_extension(entry):
    headers = entry['response']['headers']
    ctype = next((header['value'] for header in headers if header['name'].lower() == 'content-type'), '')
    # due to http://bugs.python.org/issue1043134
    if ctype == 'text/plain':
        ext = '.txt'
    else:
        # try to get an extension (and avoid adding 'None')
        ext = mimetypes.guess_extension(ctype, False) or ''
    return ext


def main():
    def extract(n, prefix):
        entry = data['log']['entries'][n]

        ext = guess_extension(entry)
        name = Path(urlparse(entry['request']['url']).path).stem
        prefix = f'{prefix}/{n + 1:03d}-{entry["response"]["status"]}{name and f"-{name}"}{ext}'

        with open(f'{prefix}-request.txt', 'wb') as fd:
            write_request(entry, fd)
        with open(f'{prefix}.response.txt', 'w') as fd:
            write_response(entry, fd)
        with open(prefix, 'wb') as fd:
            write_body(entry, fd)

    parser = ArgumentParser()
    parser.add_argument('file', type=FileType('r'), help='HAR file to extract')
    parser.add_argument('prefix')
    args = parser.parse_args()

    data = json.load(args.file)
    for n in range(len(data['log']['entries'])):
        print('extracting request', n)
        extract(n, args.prefix)


if __name__ == '__main__':
    main()
