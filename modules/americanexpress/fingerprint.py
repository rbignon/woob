# -*- coding: utf-8 -*-

# Copyright(C) 2021 Martin Lavoie
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

import re
import json
from itertools import cycle
from base64 import b64encode, b64decode

from woob.browser.pages import RawPage


def xor4(plaintext):
    """
    function za from cc.js

    Apply one of 4 transformations to
    every character of the text.

    The transformations are
    (XOR 89), (XOR 231), (XOR 225) and (XOR 55).
    """
    key = [89, 231, 225, 55]
    for p, c in zip(plaintext, cycle(key)):
        r = ord(p) ^ c
        yield chr(r)


def utf8_encode(pt):
    return ''.join(pt).encode('utf8')


def encode(content):
    """
    Takes a dictionnary and returns a base64 string representation.
    function Q in cc.js
    """
    json_content = json.dumps(content, separators=(',',':'))
    xor_content = xor4(json_content)
    utf8_content = utf8_encode(xor_content)
    return b64encode(utf8_content).decode('ascii')


def decode(cyphertext):
    """
    Inverse of encode
    """
    utf8_content = b64decode(cyphertext).decode('utf8')
    unxor_content = ''.join(xor4(utf8_content))
    return json.loads(unxor_content)


class FingerprintPage(RawPage):
    def get_t(self):
        return self.get_I()[:24]

    def get_I(self):
        """
        Random bits encoded in base64 in the javascript code
        It contained the the I variable in cc.js
        """
        regex = r'run[^,]*="([a-zA-Z0-9+=/]+)"'
        match = re.search(regex, self.text, re.DOTALL)
        assert match, "Could not find the secret I"
        return match[1]

    def make_payload_for_s2(self, tid, now):
        cookie = self.browser.session.cookies['_cc-x']
        user_agent = self.browser.session.headers['User-Agent']
        return encode(self.make_payload(tid, cookie, user_agent, now))

    def make_payload(self, tid, cookie_cc, user_agent, now):
        """
        Create a payload for the s2 verification.
        The original code in is cc.js where it has the name run.

        How to update the dictionary:
        - Locate the s2 request to cdn-path.com while
          doing an authentification in the browser.
        - Pass as argument to the decode function
          the long random line in the body of the request.
        - Update the dictionary with the result.
        - Put back the computed value for the fields that
          we support.

        In case of problem with decode, you could check if
        the magic key of xor4 has changed. If not, then
        there is no easy path for you.

        How to update the dictionary (harder way):
        - Launch Chromium
        - Toggle the breakpoint "Script First Statement" in
          "Event Listener Breakpoints/Script/Script First Statement"
        - Do an authentification
        - Continue through the breakpoints until you get
          the script cc.js
        - Find a location where you can see the new dictionary.
          Keywords:
           run : name of the function constructing the dictionary.
           stringify : function used to transform the dictionary
                       into JSON. The data should pass through it.

        If you need to take a deep dive into the cc.js script,
        I recommend using the following method.

        How to update the dictionary (hardest way):
        - Locate the cc.js request to cdn-path.com while
          doing an authentification in the browser.
          Make a copy of this file on your computer.
        - Find the javascript code that made the request to cc.js.
          You should find multiple occurence of the code
          `_cc.push` just before the request.
          The values pushed are the command to be executed
          when the javascript code (cc.js) will load.
        - Make an empty html page with a script adding the
          same command and loading your local copy of the code.
          That will allow to step through the code easily.
        - (Optional) Remove or comment the line in your
          local copy of cc.js that is sending the s2 request.
          That way you can debug without hiting the server.
        """

        time_local = now.strftime('%-m/%-d/%Y, %-I:%-M:%-S %p')
        time_string = now.strftime('%a %b %d %Y %I:%M:%S GMT+0000 (UTC)')
        unix_epoch = round(now.timestamp() * 1000)

        return {
          "sid": "ee490b8fb9a4d570",
          "tid": tid,
          "_t": self.get_I(),
          "cf_flags": 135732211,
          "cdfr": True,
          "cookie-_cc": cookie_cc,
          "timing-sc": 0,
          "time-unix-epoch-ms": unix_epoch,
          "time-local": time_local,
          "time-string": time_string,
          "time-tz-offset-minutes": 0,
          "time-tz-has-dst": "false",
          "time-tz-dst-active": "false",
          "time-tz-std-offset": 0,
          "time-tz-fixed-locale-string": "3/6/2014, 7:58:39 AM",
          "timing-ti": 1,
          "dom-local-tag": cookie_cc,
          "timing-ls": 0,
          "dom-session-tag": cookie_cc,
          "timing-ss": 0,
          "navigator.appVersion": "5.0 (X11)",
          "navigator.appName": "Netscape",
          "navigator.product": "Gecko",
          "navigator.buildID": "20181001000000",
          "navigator.platform": "Linux x86_64",
          "navigator.language": "en-US",
          "navigator.oscpu": "Linux x86_64",
          "navigator.userAgent": user_agent,
          "navigator.cookieEnabled": "true",
          "navigator.appCodeName": "Mozilla",
          "navigator.productSub": "20100101",
          "timing-no": 0,
          "navigator.hardwareConcurrency": "8",
          "touchEnabled": False,
          "navigator.automationEnabled": False,
          "navigator.doNotTrack": "1",
          "window.screen.pixelDepth": "24",
          "window.screen.height": "1080",
          "window.screen.colorDepth": "24",
          "window.menubar.visible": "true",
          "window.devicePixelRatio": "1",
          "window.history.length": "3",
          "window.screen.width": "1920",
          "timing-wo": 0,
          "window.screen.availHeight": "1080",
          "window.screen.orientation.type": "landscape-primary",
          "window.screen.orientation.angle": "0",
          "window.screen.darkMode.enabled": False,
          "timing-do": 0,
          "plugin-suffixes": "",
          "plugin-mimes": "",
          "timing-np": 0,
          "timing-iepl": 0,
          "canvas-print-100-999": "8ac8e8cd487550a157647ee7b84032290b33ca0b",
          "canvas-print-detailed-100-999": "904566a766a494df6ae8a327276267e1e38b0738",
          "timing-cp": 40,
          "timing-gief": 0,
          "js-errors": [
            "InvalidCharacterError: String contains an invalid character",
            "InvalidCharacterError: String contains an invalid character"
          ],
          "font-Times New Roman CYR": False,
          "font-Arial CYR": False,
          "font-Courier New CYR": False,
          "font-宋体": False,
          "font-Arial Cyr": False,
          "font-Times New Roman Cyr": False,
          "font-Courier New Cyr": False,
          "font-华文细黑": False,
          "font-儷黑 Pro": False,
          "font-WP CyrillicB": False,
          "font-WP CyrillicA": False,
          "font-궁서체": False,
          "font-細明體": False,
          "font-小塚明朝 Pr6N B": False,
          "font-宋体-PUA": False,
          "font-方正流行体繁体": False,
          "font-汉仪娃娃篆简": False,
          "font-돋움": False,
          "font-GaramondNo4CyrTCYLig": False,
          "font-HelveticaInseratCyr Upright": False,
          "font-HelveticaCyr Upright": False,
          "font-TL Help Cyrillic": False,
          "font-가는안상수체": False,
          "font-TLCyrillic2": False,
          "font-AGRevueCyr-Roman": False,
          "font-AGOptimaCyr": False,
          "font-HelveticaInseratCyrillicUpright": False,
          "font-HelveticaCyrillicUpright": False,
          "font-HelveticaCyrillic": False,
          "font-CyrillicRibbon": False,
          "font-CyrillicHover": False,
          "font-文鼎ＰＯＰ－４": False,
          "font-方正中倩简体": False,
          "font-创艺简中圆": False,
          "font-Zrnic Cyr": False,
          "font-Zipper1 Cyr": False,
          "font-Xorx_windy Cyr": False,
          "font-Xorx_Toothy Cyr": False,
          "font-소야솔9": False,
          "font-Цветные эмодзи Apple": False,
          "font-Chinese Generic1": False,
          "font-Korean Generic1": False,
          "font-Bullets 5(Korean)": True,
          "font-UkrainianFuturisExtra": False,
          "font-VNI-Viettay": False,
          "font-UkrainianCompact": False,
          "font-UkrainianBrushScript": False,
          "font-TiffanyUkraine": False,
          "font-Baltica_Russian-ITV": False,
          "font-Vietnamese font": False,
          "font-Unicorn Ukrainian": False,
          "font-UkrainianTimesET": False,
          "font-UkrainianCourier": False,
          "font-Tiff-HeavyUkraine": False,
          "font-䡵湧䱡渠䅲瑤敳楧渠㈰〲‭⁁汬⁲楧桴猠牥獥牶敤⹔桵⁰桡瀠噎周畦慰〲†乯牭慬ㄮ〠䍯摥⁖义⁦潲⁗楮摯睳周畦慰〲乯牭慬HungLan Artdesign - http://www.vietcomic.comVNI-Thufap2  Normalv2.0 Code VNI for WindowsVNI-Thufap2 Normal\u0002": True,
          "font-Vietnam": False,
          "font-Bwviet": False,
          "font-Soviet": False,
          "font-Soviet Expanded": False,
          "font-Soviet Bold": False,
          "font-Russian": False,
          "font-UVN Han Viet": False,
          "font-UkrainianAcademy": False,
          "font-Symbol": True,
          "font-Verdana": False,
          "font-Webdings": False,
          "font-Arial": True,
          "font-Georgia": False,
          "font-Courier New": True,
          "font-Trebuchet MS": False,
          "font-Times New Roman": True,
          "font-Impact": False,
          "font-Comic Sans MS": False,
          "font-Wingdings": False,
          "font-Tahoma": False,
          "font-Microsoft Sans Serif": False,
          "font-Arial Black": False,
          "font-Plantagenet Cherokee": False,
          "font-Arial Narrow": True,
          "font-Wingdings 2": True,
          "font-Wingdings 3": True,
          "font-Arial Unicode MS": False,
          "font-Papyrus": False,
          "font-Calibri": False,
          "font-Cambria": False,
          "font-Consolas": False,
          "font-Candara": False,
          "font-Franklin Gothic Medium": False,
          "font-Corbel": False,
          "font-Constantia": False,
          "font-Marlett": False,
          "font-Lucida Console": False,
          "font-Lucida Sans Unicode": False,
          "font-MS Mincho": False,
          "font-Arial Rounded MT Bold": False,
          "font-Palatino Linotype": False,
          "font-Batang": False,
          "font-MS Gothic": False,
          "font-PMingLiU": False,
          "font-SimSun": False,
          "font-MS PGothic": False,
          "font-MS PMincho": False,
          "font-Gulim": False,
          "font-Cambria Math": False,
          "font-Garamond": False,
          "font-Bookman Old Style": False,
          "font-Book Antiqua": False,
          "font-Century Gothic": False,
          "font-Monotype Corsiva": False,
          "font-Courier": False,
          "font-Meiryo": False,
          "font-Century": False,
          "font-MT Extra": False,
          "font-MS Reference Sans Serif": False,
          "font-MS Reference Specialty": False,
          "font-Mistral": False,
          "font-Bookshelf Symbol 7": True,
          "font-Lucida Bright": False,
          "font-Cooper Black": False,
          "font-Modern No. 20": True,
          "font-Bernard MT Condensed": False,
          "font-Bell MT": False,
          "font-Baskerville Old Face": False,
          "font-Bauhaus 93": True,
          "font-Britannic Bold": False,
          "font-Wide Latin": False,
          "font-Playbill": False,
          "font-Harrington": False,
          "font-Onyx": False,
          "font-Footlight MT Light": False,
          "font-Stencil": False,
          "font-Colonna MT": False,
          "font-Matura MT Script Capitals": False,
          "font-Copperplate Gothic Bold": False,
          "font-Copperplate Gothic Light": False,
          "font-Edwardian Script ITC": False,
          "font-Rockwell": False,
          "font-Curlz MT": False,
          "font-Engravers MT": False,
          "font-Rockwell Extra Bold": False,
          "font-Haettenschweiler": False,
          "font-MingLiU": False,
          "font-Mongolian Baiti": False,
          "font-Microsoft Yi Baiti": False,
          "font-Microsoft Himalaya": False,
          "font-SimHei": False,
          "font-SimSun-ExtB": False,
          "font-PMingLiU-ExtB": False,
          "font-MingLiU-ExtB": False,
          "font-MingLiU_HKSCS-ExtB": False,
          "font-MingLiU_HKSCS": False,
          "font-Gabriola": False,
          "font-Goudy Old Style": False,
          "font-Calisto MT": False,
          "font-Imprint MT Shadow": False,
          "font-Gill Sans Ultra Bold": False,
          "font-Century Schoolbook": False,
          "font-Gloucester MT Extra Condensed": False,
          "font-Perpetua": False,
          "font-Franklin Gothic Book": False,
          "font-Brush Script MT": False,
          "font-Microsoft Tai Le": False,
          "font-Gill Sans MT": False,
          "font-Tw Cen MT": False,
          "font-Lucida Handwriting": False,
          "font-Lucida Sans": False,
          "font-Segoe UI": False,
          "font-Lucida Fax": False,
          "font-MV Boli": False,
          "font-Sylfaen": False,
          "font-Estrangelo Edessa": False,
          "font-Mangal": True,
          "font-Gautami": False,
          "font-Tunga": False,
          "font-Shruti": False,
          "font-Raavi": False,
          "font-Latha": False,
          "font-Lucida Calligraphy": False,
          "font-Lucida Sans Typewriter": False,
          "font-Kartika": False,
          "font-Vrinda": False,
          "font-Perpetua Titling MT": False,
          "font-Cordia New": True,
          "font-Angsana New": True,
          "font-IrisUPC": False,
          "font-CordiaUPC": True,
          "font-FreesiaUPC": False,
          "font-Miriam": True,
          "font-Traditional Arabic": False,
          "font-Miriam Fixed": True,
          "font-JasmineUPC": False,
          "font-KodchiangUPC": False,
          "font-LilyUPC": False,
          "font-Levenim MT": True,
          "font-EucrosiaUPC": False,
          "font-DilleniaUPC": False,
          "font-Rod": False,
          "font-Narkisim": False,
          "font-FrankRuehl": True,
          "font-David": True,
          "font-Andalus": False,
          "font-Browallia New": True,
          "font-AngsanaUPC": True,
          "font-BrowalliaUPC": True,
          "font-MS UI Gothic": False,
          "font-Aharoni": True,
          "font-Simplified Arabic Fixed": False,
          "font-Simplified Arabic": False,
          "font-GulimChe": False,
          "font-Dotum": False,
          "font-DotumChe": False,
          "font-GungsuhChe": False,
          "font-Gungsuh": False,
          "font-BatangChe": False,
          "font-Meiryo UI": False,
          "font-NSimSun": False,
          "font-Segoe Script": False,
          "font-Segoe Print": False,
          "font-DaunPenh": False,
          "font-Kalinga": False,
          "font-Iskoola Pota": False,
          "font-Euphemia": False,
          "font-DokChampa": False,
          "font-Nyala": False,
          "font-MoolBoran": False,
          "font-Leelawadee": False,
          "font-Gisha": False,
          "font-Microsoft Uighur": False,
          "font-Arabic Typesetting": False,
          "font-Malgun Gothic": False,
          "font-Microsoft JhengHei": False,
          "font-DFKai-SB": False,
          "font-Microsoft YaHei": False,
          "font-FangSong": False,
          "font-KaiTi": False,
          "font-Helvetica": False,
          "font-Segoe UI Light": False,
          "font-Segoe UI Semibold": False,
          "font-Andale Mono": False,
          "font-Palatino": False,
          "font-Geneva": False,
          "font-Monaco": False,
          "font-Lucida Grande": False,
          "font-Gill Sans": False,
          "font-Helvetica Neue": False,
          "font-Baskerville": False,
          "font-Hoefler Text": False,
          "font-Thonburi": False,
          "font-Herculanum": False,
          "font-Apple Chancery": False,
          "font-Didot": False,
          "font-Zapf Dingbats": False,
          "font-Apple Symbols": False,
          "font-Copperplate": False,
          "font-American Typewriter": False,
          "font-Zapfino": False,
          "font-Cochin": False,
          "font-Chalkboard": False,
          "font-Sathu": False,
          "font-Osaka": False,
          "font-BiauKai": False,
          "font-Segoe UI Symbol": False,
          "font-Aparajita": False,
          "font-Krungthep": False,
          "font-Ebrima": False,
          "font-Silom": False,
          "font-Kokila": False,
          "font-Shonar Bangla": False,
          "font-Sakkal Majalla": False,
          "font-Microsoft PhagsPa": False,
          "font-Microsoft New Tai Lue": False,
          "font-Khmer UI": False,
          "font-Vijaya": False,
          "font-Utsaah": False,
          "font-Charcoal CY": False,
          "font-Ayuthaya": False,
          "font-InaiMathi": False,
          "font-Euphemia UCAS": False,
          "font-Vani": False,
          "font-Lao UI": False,
          "font-GB18030 Bitmap": False,
          "font-KufiStandardGK": False,
          "font-Geeza Pro": False,
          "font-Chalkduster": False,
          "font-Tempus Sans ITC": False,
          "font-Kristen ITC": False,
          "font-Apple Braille": False,
          "font-Juice ITC": False,
          "font-STHeiti": False,
          "font-LiHei Pro": False,
          "font-DecoType Naskh": False,
          "font-New Peninim MT": True,
          "font-Nadeem": False,
          "font-Mshtakan": False,
          "font-Gujarati MT": False,
          "font-Devanagari MT": False,
          "font-Arial Hebrew": False,
          "font-Corsiva Hebrew": False,
          "font-Baghdad": False,
          "font-STFangsong": False,
          "timing-kf": 45,
          "webgl-supported": False,
          "timing-wgl": 0,
          "timing-sync-collection": 90,
          "timing-generation": 2,
          "timing-wr": 177
        }
