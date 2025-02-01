# Copyright(C) 2023 Powens
#
# flake8: compatible

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


import base64
from io import BytesIO

from woob.tools.captcha.virtkeyboard import SimpleVirtualKeyboard


class ESAmundiVirtKeyboard(SimpleVirtualKeyboard):
    symbols = {
        "0": (
            "c52d792420f50aad8a67aa5a195a4b71",
            "6d0ef26ea44efc0271b556c8714cdab8",
            "d8759fed56704adeffa850f8820b7199",
            "878f9ffc62af5b26d59494ae4d9fb74b",
            "79080c81ba83923af7f17d26b8901fd8",
            "8f032ed507eebb0583e00e408626ba0e",
            "a39c2fbe668984b7ab3d62efea95a4ef",
            "1a42437cbea82dda5dc19b2ef56c08b1",
            "aababb52093904e1af0780fc9b482812",
            "9b2c2831ae741442f7882dd661626fc7",
            "a7a594b898f6953955d49fc856ad753f",
            "bf9370633816bcb1acf0bb829d29c0a0",
            "ef52e77262455c3c139ee022b12b6e6d",
        ),
        "1": (
            "f38053babe50d398ad637ed7bcfadd23",
            "6f9b40f279a24b5ab72186588d86d9c0",
            "3ef5f4abc51a8a27aa69fd3d5b4cebd5",
            "721ce5c871745573a452f3aaa6a862af",
            "2c36ba422057d36b897a27479c49892c",
            "8d8bbc42953e2a128a5dfa9fc29f6eef",
            "0c6b060f4a746a7d0a41a5763b1fbc7f",
            "0559742827d7fd057e0a251ca5c5fb8c",
            "596880933ad1419cf0ef86385c5dbdea",
            "fd30f81fbf955a742c6475033e59d5d9",
            "7637e06f897e51ed403ff0923a24249c",
            "f1139ad6caa3c50f89e2c17f9b238f35",
            "c1d18795f6e4722841464dacba115661",
        ),
        "2": (
            "d93b61347b890ef7df05cc5e1e8801bd",
            "45cea12a492cc2a6cce090562ab3f663",
            "531bf9713c9f37fb22c124867c1c2040",
            "79811fe9311637d2a40e73e74bea4f4c",
            "052ec4a212b6aa7323c4fef7738ecd72",
            "f0cfdb209ad508b0d24cb582fbc01b05",
            "5f82b6f838ae65c0c38944da391a758c",
            "da248a943b292bd0526ea8cedda312a2",
            "ad909091d65dc509ce93c2888a94b526",
            "6e47cf930bf58476a6e32a4319542aa7",
            "60aa66e9f326db99c764413c57381d9d",
            "7c8ec36ffc68df8a8977f8ba158366f2",
            "36b01df2c75d7bfe02565203ec55e707",
        ),
        "3": (
            "00d653c1e786b20080fa8f86be515113",
            "a5e61e93d4ea9a8c3a604834f4e13468",
            "339012a876a1ae6b88d1a06701ee2387",
            "61daeb4d6717f25b0bf6efc05535ea10",
            "322574489a1513d92f90aabbf940346e",
            "6e3d448db17eec928c2889e4a75e69e3",
            "38a5955df1dff109fae77b183d480962",
            "fcf7d285c89bf6d1b687a1a27e00e67a",
            "13685c22791512fbf5594b443a1b0eb7",
            "3dc4b8dd59da0258aaae6af39b471ef3",
            "2b9f6c9c3339112e94d02eaefeccc5b6",
            "0343153e59ed97db11e756fb0004f680",
            "c4ab760abd7a89d844093176a12d4893",
        ),
        "4": (
            "2f5b60b51779cb1b0f548be9ec134b42",
            "bd3eed76e45caacb063f281ca954413b",
            "b7233e7f26706f91c76e96df858b6f7f",
            "0fd26faf69c0e9811290dfa0ca0c827f",
            "c3f9eec5358062ec161a337f77856ce6",
            "7bc849f754e0095d0c3660ad6421983d",
            "4c90ed8be81736addcbde2f2613ecc5b",
            "3d1255f22156d7bb941f228cf8b0f6c4",
            "6f99aab35bebefba21727c7a820b5f58",
            "b0217da514d105bb29b3d84aed2b76fd",
            "0ca6f762c631e271f8bc5141fabfa34a",
            "7a492c80d5db526523e4c75f07f9d59d",
            "f3037ad69b9390dc870205e106219669",
        ),
        "5": (
            "10ed51da2fde546772ed97c942871e42",
            "b8c3c70e4975d72e10ea57fa1bfb8523",
            "c7a797ad2ddeba49e9e2572a1fdf6b99",
            "08ecea5cd75433b7f22e3af75652d21c",
            "a48893a66a761a2bb339f810d07636e6",
            "891c80dd791ce4414272c15c6d130ebf",
            "750de6a95d73d390449fe0d8a49f0378",
            "52cfc01b24d5fc083aea487973f3d773",
            "5ac68220c737d5331440e28792e62e84",
            "2267f4b21e3e43bc68bf913b58023376",
            "9eb76988dde7e6963c4c0e46555e2759",
            "ccffea6a07584f48c084af8ea578d646",
            "a6a32dd5ae0977703cf0ac15afc190bc",
        ),
        "6": (
            "15c116193e708c732bacaa8df8bc7de7",
            "a5e61e93d4ea9a8c3a604834f4e13468",
            "3a901bff6d04d5ec56ff5daca6e5447e",
            "858a6aaf1bdd884c52444fe2bd001202",
            "6c2bd071609fec1a3e47420df45c74b0",
            "8e52882bcc105addf0cbdfb022439d47",
            "b4b1ff0a0c8a5b48b2843bb0b85d46ae",
            "895c85e96c60282c0e062042022292a9",
            "0c7aeb4da9a63c463522bd044c5e03f4",
            "068869a8da8d3350b5aba5fc7974eccb",
            "df6dbd3c998eb8f0934af13deb5f816a",
            "8a60a0ea1d3ca90bb0a23e4d2214041b",
            "c07a9ca02dd249a05b452739e7cf3f69",
        ),
        "7": (
            "d0a670e31f27817d538501a85f2d49ec",
            "5fe3218925d7eb2ca7af20363c2844cd",
            "504e5afff16d7e1f0451579f1dd9d9d5",
            "80410c1bf7b1689089538dfb0db1b666",
            "3b1c2c70cf8959b223c194c796b256bb",
            "c055a5104b82e0d88fa0bb2ebb8b7bec",
            "dabb2df5f9307c304496254b7374eb22",
            "00ee47abcc93f68fe52a70deb88da46e",
            "726ded975ed84d6ef837cbb5648f97d5",
            "c3754d8774a1186d048b241e99943bbc",
            "1d837b17592e8cf782ed7de2b02016b1",
            "f718f833478045809fd29d73dfb302cf",
            "df763ebe92968c17eaa5b97a84aba257",
        ),
        "8": (
            "5e6930c12ad947550c319a41df066cd9",
            "bd3eed76e45caacb063f281ca954413b",
            "af7852b52a8f3fa8a659382fd03f0c1d",
            "fbe20c7f35b68205e674c6e46a2035b3",
            "668cb0da6e65af530f5f90f6296425ce",
            "f2ecb185a0e75d908dd16bc3caceea76",
            "29453a8672edab5cff5b35d83e242857",
            "d5a9c20820e4f2d70cb75f578cdd8ad1",
            "1b23565c71769383a62c7d161d4f20f5",
            "db20519e941c7f79915c2c9113739f10",
            "f311bef7e324ae09c14362768b21ce32",
            "28dd98545832c587fd4d25c194b362a5",
            "e51d754619d1d70c0a7a3b8a8a704ffa",
        ),
        "9": (
            "23756eceb8350d46b2cb1e1d7b6ae3ec",
            "c73a225b1e9731e5b2eb903d493bae5e",
            "c61bd57f3573fecda4de63ee3563ce4a",
            "df27eef7806c02e5ebc25d39a0c59170",
            "08ed18417136dc88723a5b95e2377fcc",
            "f74586a7b4a20732de85a68b809c40f4",
            "ee202b236276d06fe8bed7301bf571a4",
            "ed0136c48f7370476e5769bdea6bc345",
            "04141d46eccd35efa44ea022171ce92e",
            "bd0bb1634c4696ac262a7c7f57e33e2f",
            "62cca6f12a368e2e5a4d8495e3089065",
            "80c426ff8ffa1282c6da5795932da62b",
            "e1e9ef14c6cc46c9bc4217203f547441",
        ),
    }

    matching_symbols_coords = {
        "0": (0, 0, 65, 50),
        "1": (70, 0, 135, 50),
        "2": (140, 0, 205, 50),
        "3": (210, 0, 275, 50),
        "4": (280, 0, 345, 50),
        "5": (0, 55, 65, 105),
        "6": (70, 55, 135, 105),
        "7": (140, 55, 205, 105),
        "8": (210, 55, 275, 105),
        "9": (280, 55, 345, 105),
    }

    def __init__(self, browser, image_base64):
        image_file = BytesIO(base64.b64decode(image_base64))

        super().__init__(
            image_file,
            cols=5,
            rows=2,
            matching_symbols_coords=self.matching_symbols_coords,
        )
