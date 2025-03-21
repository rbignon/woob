# Copyright(C) 2013 Julien Veyssier
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

from woob.capabilities.base import empty
from woob.capabilities.subtitle import CapSubtitle
from woob.tools.application.formatters.iformatter import IFormatter, PrettyFormatter
from woob.tools.application.repl import ReplApplication, defaultcount


__all__ = ["AppSubtitles"]

LANGUAGE_CONV = {
    "ar": "ara",
    "eo": "epo",
    "ga": "",
    "ru": "rus",
    "af": "",
    "et": "est",
    "it": "ita",
    "sr": "scc",
    "sq": "alb",
    "tl": "",
    "ja": "jpn",
    "sk": "slo",
    "hy": "arm",
    "fi": "fin",
    "kn": "",
    "sl": "slv",
    "az": "",
    "fr": "fre",
    "ko": "kor",
    "es": "spa",
    "eu": "baq",
    "gl": "glg",
    "la": "",
    "sw": "swa",
    "be": "",
    "ka": "geo",
    "lv": "lav",
    "sv": "swe",
    "bn": "ben",
    "de": "ger",
    "lt": "lit",
    "ta": "",
    "bg": "bul",
    "gr": "ell",
    "mk": "mac",
    "te": "tel",
    "ca": "cat",
    "gu": "",
    "ms": "may",
    "th": "tha",
    "zh": "chi",
    "ht": "",
    "mt": "",
    "tr": "tur",
    "hr": "hrv",
    "iw": "heb",
    "no": "nor",
    "uk": "ukr",
    "cz": "cze",
    "hi": "hin",
    "fa": "per",
    "ur": "urd",
    "da": "dan",
    "hu": "hun",
    "pl": "pol",
    "vi": "vie",
    "nl": "dut",
    "is": "ice",
    "pt": "por",
    "cy": "",
    "en": "eng",
    "id": "ind",
    "ro": "rum",
    "yi": "",
}


def sizeof_fmt(num):
    for x in ["bytes", "KB", "MB", "GB", "TB"]:
        if num < 1024.0:
            return f"{num:<4.1f}{x}"
        num /= 1024.0


class SubtitleInfoFormatter(IFormatter):
    MANDATORY_FIELDS = ("id", "name", "url", "description")

    def format_obj(self, obj, alias):
        result = f"{self.BOLD}{obj.name}{self.NC}\n"
        result += "ID: %s\n" % obj.fullid
        result += "URL: %s\n" % obj.url
        if not empty(obj.language):
            result += "LANG: %s\n" % obj.language
        if not empty(obj.nb_cd):
            result += "NB CD: %s\n" % obj.nb_cd
        result += f"\n{self.BOLD}Description{self.NC}\n"
        result += "%s" % obj.description
        return result


class SubtitleListFormatter(PrettyFormatter):
    MANDATORY_FIELDS = ("id", "name")

    def get_title(self, obj):
        return obj.name

    def get_description(self, obj):
        result = "lang : %s" % obj.language
        result += " ; %s CD" % obj.nb_cd
        if not empty(obj.url):
            result += " ; url : %s" % obj.url
        return result


class AppSubtitles(ReplApplication):
    APPNAME = "subtitles"
    VERSION = "3.7"
    COPYRIGHT = "Copyright(C) 2013-YEAR Julien Veyssier"
    DESCRIPTION = "Console application allowing to search for subtitles on various services " "and download them."
    SHORT_DESCRIPTION = "search and download subtitles"
    CAPS = CapSubtitle
    EXTRA_FORMATTERS = {"subtitle_list": SubtitleListFormatter, "subtitle_info": SubtitleInfoFormatter}
    COMMANDS_FORMATTERS = {"search": "subtitle_list", "info": "subtitle_info"}

    def complete_info(self, text, line, *ignored):
        args = line.split(" ")
        if len(args) == 2:
            return self._complete_object()

    def do_info(self, id):
        """
        info ID

        Get information about a subtitle.
        """

        subtitle = self.get_object(id, "get_subtitle")
        if not subtitle:
            print("Subtitle not found: %s" % id, file=self.stderr)
            return 3

        self.start_format()
        self.format(subtitle)

    def complete_download(self, text, line, *ignored):
        args = line.split(" ", 2)
        if len(args) == 2:
            return self._complete_object()
        elif len(args) >= 3:
            return self.path_completer(args[2])

    def do_download(self, line):
        """
        download ID [FILENAME]

        Get the subtitle or archive file.
        FILENAME is where to write the file. If FILENAME is '-',
        the file is written to stdout.
        """
        id, dest = self.parse_command_args(line, 2, 1)

        subtitle = self.get_object(id, "get_subtitle")
        if not subtitle:
            print("Subtitle not found: %s" % id, file=self.stderr)
            return 3

        if dest is None:
            ext = subtitle.ext
            if empty(ext):
                ext = "zip"
            dest = f"{subtitle.name}.{ext}"

        for buf in self.do("get_subtitle_file", subtitle.id, backends=subtitle.backend):
            if buf:
                if dest == "-":
                    self.stdout.buffer.write(buf)
                else:
                    try:
                        with open(dest, "wb") as f:
                            f.write(buf)
                    except OSError as e:
                        print(f'Unable to write file in "{dest}": {e}', file=self.stderr)
                        return 1
                    else:
                        print("Saved to %s" % dest)
                return

    @defaultcount(10)
    def do_search(self, line):
        """
        search language [PATTERN]

        Search subtitles.

        Language  Abbreviation
        ----------------------
        Arabic      ar          Esperanto   eo          Irish       ga          Russian     ru
        Afrikaans   af          Estonian    et          Italian     it          Serbian     sr
        Albanian    sq          Filipino    tl          Japanese    ja          Slovak      sk
        Armenian    hy          Finnish     fi          Kannada     kn          Slovenian   sl
        Azerbaijani az          French      fr          Korean      ko          Spanish     es
        Basque      eu          Galician    gl          Latin       la          Swahili     sw
        Belarusian  be          Georgian    ka          Latvian     lv          Swedish     sv
        Bengali     bn          German      de          Lithuanian  lt          Tamil       ta
        Bulgarian   bg          Greek       gr          Macedonian  mk          Telugu      te
        Catalan     ca          Gujarati    gu          Malay       ms          Thai        th
        Chinese     zh          Haitian     ht          Maltese     mt          Turkish     tr
        Croatian    hr          Hebrew      iw          Norwegian   no          Ukrainian   uk
        Czech       cz          Hindi       hi          Persian     fa          Urdu        ur
        Danish      da          Hungaric    hu          Polish      pl          Vietnamese  vi
        Dutch       nl          Icelandic   is          Portuguese  pt          Welsh       cy
        English     en          Indonesian  id          Romanian    ro          Yiddish     yi
        ----------------------
        """
        language, pattern = self.parse_command_args(line, 2, 1)
        self.change_path(["search"])
        if not pattern:
            pattern = None

        self.start_format(pattern=pattern)
        for subtitle in self.do("iter_subtitles", language=language, pattern=pattern):
            self.cached_format(subtitle)
