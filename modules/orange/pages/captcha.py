# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020 Budget Insight

import json
import re

from io import BytesIO
from PIL import Image

from weboob.browser.pages import HTMLPage
from weboob.exceptions import BrowserUnavailable

from .captcha_symbols import CAPTCHA_SYMBOLS


class OrangeCaptchaHandler(object):
    symbols = CAPTCHA_SYMBOLS

    def __init__(self, logger, indications, images):
        self.logger = logger
        self.indications = indications  # it contains 6 elements actually
        self.fingerprints = {}

        for value, image_data in images.items():
            symbol = self.get_symbol_from_image_data(image_data)
            best_indication, best_index = self.get_best_indication(symbol)
            self.fingerprints[value] = {
                'value': value,
                'symbol': symbol,
                'best_indication': best_indication,
                'best_index': best_index,
            }

    @staticmethod
    def get_symbol_from_image_data(image_data):
        img = Image.open(BytesIO(image_data))
        img = img.convert('RGB')

        small_image = img.resize((10, 10))

        matrix = small_image.load()
        symbol = ""

        for y in range(0, 10):
            for x in range(0, 10):
                (r, g, b) = matrix[x, y]
                # If the pixel is "white" enough
                if r + g + b > 384:
                    symbol += "1"
                else:
                    symbol += "0"

        return symbol

    @staticmethod
    def _get_similar_index(ref, value):
        cpt = 0
        for r, v in zip(ref, value):
            if r == v:
                cpt += 1

        return cpt

    def get_best_indication(self, symbol):
        # indication is 'avion', 'chat', 'fleur', etc...
        # this function tries to find which one is the good one based on his symbol
        best_index = 0
        best_indication = None
        for key, symbols in self.symbols.items():
            for sym in symbols:
                index = self._get_similar_index(sym, symbol)
                if index > best_index:
                    best_index = index
                    best_indication = key

        return best_indication, best_index

    def get_captcha_response(self):
        captcha_response = []
        cache = {}  # because we can have several time same indication in list: 'avion', 'fleur', 'avion', ...

        for indication in self.indications:
            best_index = 0
            best_indication = None
            good_key = None

            if indication in cache.keys():
                good_key = cache[indication]['value']
                best_indication = cache[indication]['best_indication']
                best_index = cache[indication]['best_index']
            else:
                for key, value in self.fingerprints.items():
                    if value['best_indication'] == indication and value['best_index'] > best_index:
                        cache[indication] = value
                        best_index = value['best_index']
                        best_indication = value['best_indication']
                        good_key = key

            if not good_key:
                # we have failed to detect which key is the good one
                raise BrowserUnavailable()

            if best_index < 90:
                # index is always in [0:100], but when < 90 there is a strong chance image is not what we think
                # we probably have failed to identify it correctly, maybe because we don't know it
                # IF image isn't known
                #     add his symbol
                # ELSE
                #     improve matching algorithm to have a better matching,
                #     but in that case DO NOT FORGET to rebuild all symbols
                self.logger.error('best_indication: %s best_index: %d', best_indication, best_index)
                raise BrowserUnavailable()
            elif best_index < 95:
                # there is a small chance image is not what we think it is, but not sure at all
                # take the chance anyway
                self.logger.warning('best_indication: %s best_index: %d', best_indication, best_index)

            captcha_response.append(good_key)

        return captcha_response


class CaptchaPage(HTMLPage):
    def get_captcha_data(self):
        scripts = self.doc.xpath('//script[contains(text(), "captchaOptions")]')
        if not scripts:
            return

        script = scripts[0]
        value = re.search(r'config: (.*),', script.text).group(1)
        data = json.loads(value)

        urls = {}
        for row in data['rows']:
            for col in row:
                url = 'https:' + col['data']
                urls[col['value']] = url

        return {
            'indications': data['indications'],
            'urls': urls,
        }

    def download_images(self, data_captcha):
        images = {}
        for key, url in data_captcha['urls'].items():
            images[key] = self.browser.open(url).content

        return images
