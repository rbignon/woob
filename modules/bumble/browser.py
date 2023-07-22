# Copyright(C) 2022      Roger Philibert
#
# This file is part of a woob module.
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

import time
import hashlib
import json

from woob.browser.browsers import APIBrowser, StatesMixin, need_login
from woob.exceptions import OTPSentType, SentOTPQuestion, BrowserIncorrectPassword, BrowserHTTPError


class BumbleBrowser(StatesMixin, APIBrowser):
    BASEURL = 'https://eu1.bumble.com/mwebapi.phtml'

    __states__ = ('my_id', '_my_name')

    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.phone = config['phone'].get()
        self.counter = 0
        self.my_id = ""
        self.my_user = None
        self._my_name = None
        self.session.headers.update({
            'Origin': 'https://bumble.com',
            'Referer': 'https://bumble.com/get-started',
            'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="102"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Linux"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'X-Message-type': '2',
            'X-Desktop-web': '1',
            'X-Pingback': 'a19249be9c3b5ed8998469dd46312a46',
            'x-use-session-cookie': '1',
            'Content-Type': 'application/json',
            'X-Message-Type': '2',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
        })

    @staticmethod
    def sign(body):
        string = body + "whitetelevisionbulbelectionroofhorseflying"
        result = hashlib.md5(string.encode())
        return result.hexdigest()

    @property
    def my_name(self):
        if not self._my_name:
            self._my_name = self.get_user(self.my_id)['name']
        return self._my_name


    @property
    def logged(self):
        return 'session' in self.session.cookies

    def do_login(self):
        pincode = self.config['pincode'].get()
        if not pincode:
            if 'session' in self.session.cookies:
                return
            self.app_startup()
            self.submit_phone()
            self.confirm_screen_story()
            self.update_session()
            raise SentOTPQuestion('pincode',
                                  medium_type=OTPSentType.SMS,
                                  message='Enter the PIN code')
        else:
            self.check_phone_pin(pincode)

    def call(self, url, data, message_type=None):
        self.counter += 1
        data['message_id'] = self.counter
        data = json.dumps(data)
        headers = {'X-Pingback': self.sign(data)}
        if message_type:
            headers['X-Message-type'] = str(message_type)
        r = self.open(url, data=data, headers=headers)
        if 'X-User-id' in r.headers:
            self.my_id = r.headers['X-User-id']

        doc = r.json()

        if 'server_error_message' in doc['body'][-1]:
            message = doc['body'][-1]['server_error_message']['error_message']
            if doc['body'][-1]['server_error_message']['error_code'] == '1':
                self.session.cookies.clear()
                raise BrowserIncorrectPassword(message)
            else:
                raise BrowserHTTPError(message)
        return doc

    def app_startup(self):
        data = {
            "$gpb": "badoo.bma.BadooMessage",
            "body": [
                {
                    "message_type": 2,
                    "server_app_startup": {
                        "app_build": "MoxieWebapp",
                        "app_name": "moxie",
                        "app_version": "1.0.0",
                        "can_send_sms": False,
                        "user_agent": self.session.headers['User-Agent'],
                        "screen_width": 1680,
                        "screen_height": 1050,
                        "language": 0,
                        "is_cold_start": True,
                        "external_provider_redirect_url": "https://bumble.com/static/external-auth-result.html?",
                        "locale": "fr",
                        "system_locale": "en-US",
                        "app_platform_type": 5,
                        "app_product_type": 400,
                        "device_info": {
                            "webcam_available": True,
                            "form_factor": 3
                        },
                        "build_configuration": 2,
                        "build_fingerprint": "26902",
                        "supported_features": [
                            141,
                            145,
                            11,
                            15,
                            1,
                            2,
                            13,
                            46,
                            4,
                            248,
                            6,
                            18,
                            155,
                            70,
                            160,
                            140,
                            130,
                            189,
                            187,
                            220,
                            223,
                            180,
                            197,
                            161,
                            232,
                            29,
                            227,
                            237,
                            239,
                            254,
                            190,
                            290,
                            291,
                            296,
                            250,
                            264,
                            294,
                            295,
                            310,
                            100,
                            148,
                            262
                        ],
                        "supported_minor_features": [
                            472,
                            317,
                            2,
                            216,
                            244,
                            232,
                            19,
                            130,
                            225,
                            246,
                            31,
                            125,
                            183,
                            114,
                            254,
                            8,
                            9,
                            83,
                            41,
                            427,
                            115,
                            288,
                            420,
                            477,
                            93,
                            226,
                            413,
                            267,
                            39,
                            290,
                            398,
                            453,
                            180,
                            281,
                            40,
                            455,
                            280,
                            499,
                            471,
                            397,
                            411,
                            352,
                            447,
                            146,
                            469,
                            118,
                            63,
                            391,
                            523,
                            293,
                            431,
                            620,
                            574,
                            405,
                            547,
                            451,
                            571,
                            319,
                            297,
                            558,
                            394,
                            593,
                            628,
                            603,
                            602,
                            537,
                            305,
                            561,
                            324,
                            554,
                            505,
                            696,
                            576,
                            707,
                            726,
                            624,
                            797,
                            309,
                            329,
                            307,
                            553
                        ],
                        "supported_notifications": [
                            83,
                            73,
                            3,
                            72,
                            49,
                            46,
                            109,
                            81,
                            44,
                            96,
                            89
                        ],
                        "supported_payment_providers": [
                            26,
                            100,
                            35,
                            100001,
                            191
                        ],
                        "supported_promo_blocks": [
                            {
                                "context": 92,
                                "position": 13,
                                "types": [
                                    71
                                ]
                            },
                            {
                                "context": 45,
                                "position": 21,
                                "types": [
                                    148
                                ]
                            },
                            {
                                "context": 89,
                                "position": 5,
                                "types": [
                                    160,
                                    358
                                ]
                            },
                            {
                                "context": 8,
                                "position": 13,
                                "types": [
                                    111,
                                    112,
                                    113
                                ]
                            },
                            {
                                "context": 53,
                                "position": 18,
                                "types": [
                                    136,
                                    93,
                                    12
                                ]
                            },
                            {
                                "context": 45,
                                "position": 18,
                                "types": [
                                    327
                                ]
                            },
                            {
                                "context": 45,
                                "position": 15,
                                "types": [
                                    410,
                                    93,
                                    134,
                                    135,
                                    136,
                                    137,
                                    327,
                                    308,
                                    309,
                                    334,
                                    187,
                                    61,
                                    422,
                                    423
                                ]
                            },
                            {
                                "context": 10,
                                "position": 1,
                                "types": [
                                    265,
                                    266,
                                    286
                                ]
                            },
                            {
                                "context": 148,
                                "position": 21,
                                "types": [
                                    179,
                                    180,
                                    283
                                ]
                            },
                            {
                                "context": 26,
                                "position": 13,
                                "types": [
                                    354
                                ]
                            },
                            {
                                "context": 26,
                                "position": 4,
                                "types": [
                                    355,
                                    356
                                ]
                            },
                            {
                                "context": 26,
                                "position": 1,
                                "types": [
                                    354
                                ]
                            },
                            {
                                "context": 26,
                                "position": 18,
                                "types": [
                                    357
                                ]
                            },
                            {
                                "context": 130,
                                "position": 13,
                                "types": [
                                    268,
                                    267
                                ]
                            },
                            {
                                "context": 113,
                                "position": 1,
                                "types": [
                                    228
                                ]
                            },
                            {
                                "context": 3,
                                "position": 1,
                                "types": [
                                    80,
                                    423
                                ]
                            },
                            {
                                "context": 3,
                                "position": 4,
                                "types": [
                                    80,
                                    228,
                                    423
                                ]
                            },
                            {
                                "context": 119,
                                "position": 1,
                                "types": [
                                    80,
                                    282,
                                    81,
                                    90,
                                    422,
                                    140
                                ]
                            },
                            {
                                "context": 43,
                                "position": 1,
                                "types": [
                                    96,
                                    307
                                ]
                            },
                            {
                                "context": 43,
                                "position": 18,
                                "types": [
                                    369
                                ]
                            },
                            {
                                "context": 119,
                                "position": 18,
                                "types": [
                                    369
                                ]
                            },
                            {
                                "context": 10,
                                "position": 18,
                                "types": [
                                    358,
                                    174
                                ]
                            },
                            {
                                "context": 10,
                                "position": 8,
                                "types": [
                                    358
                                ]
                            },
                            {
                                "context": 26,
                                "position": 16,
                                "types": [
                                    286,
                                    371
                                ]
                            },
                            {
                                "context": 10,
                                "position": 6,
                                "types": [
                                    286,
                                    373,
                                    372
                                ]
                            },
                            {
                                "context": 246,
                                "position": 13,
                                "types": [
                                    404
                                ]
                            }
                        ],
                        "supported_user_substitutes": [
                            {
                                "context": 1,
                                "types": [
                                    3
                                ]
                            }
                        ],
                        "supported_onboarding_types": [
                            9
                        ],
                        "user_field_filter_client_login_success": {
                            "projection": [
                                210,
                                220,
                                230,
                                200,
                                91,
                                890,
                                340,
                                10,
                                11,
                                231,
                                71,
                                93,
                                100
                            ]
                        },
                        "a_b_testing_settings": {
                            "tests": [
                                {
                                    "test_id": "bumble__gifs_with_old_input"
                                }
                            ]
                        },
                        "dev_features": [
                            "bumble_bizz",
                            "bumble_snooze",
                            "bumble_questions",
                            "bumble__pledge",
                            "bumble__request_photo_verification",
                            "bumble_moves_making_impact_",
                            "bumble__photo_verification_filters",
                            "bumble_gift_cards",
                            "bumble__antighosting_xp_dead_chat_followup",
                            "bumble_private_detector",
                            "bumble_distance_expansion",
                            "bumble_live_in_the_hive"
                        ],
                        "device_id": "cdbbb751-1a75-40d7-abe2-f747a108f5fb",
                        "supported_screens": [
                            {
                                "type": 23,
                                "version": 4
                            },
                            {
                                "type": 26,
                                "version": 0
                            },
                            {
                                "type": 13,
                                "version": 0
                            },
                            {
                                "type": 14,
                                "version": 0
                            },
                            {
                                "type": 15,
                                "version": 0
                            },
                            {
                                "type": 16,
                                "version": 0
                            },
                            {
                                "type": 18,
                                "version": 0
                            },
                            {
                                "type": 19,
                                "version": 0
                            },
                            {
                                "type": 20,
                                "version": 0
                            },
                            {
                                "type": 21,
                                "version": 0
                            },
                            {
                                "type": 25,
                                "version": 0
                            },
                            {
                                "type": 27,
                                "version": 0
                            },
                            {
                                "type": 28,
                                "version": 0
                            },
                            {
                                "type": 57,
                                "version": 0
                            },
                            {
                                "type": 29,
                                "version": 1
                            },
                            {
                                "type": 69,
                                "version": 0
                            },
                            {
                                "type": 297,
                                "version": 0
                            },
                            {
                                "type": 298,
                                "version": 0
                            },
                            {
                                "type": 92,
                                "version": 0
                            }
                        ],
                        "supported_landings": [
                            {
                                "source": 25,
                                "params": [
                                    20,
                                    3
                                ],
                                "search_settings_types": [
                                    3
                                ]
                            }
                        ],
                        "app_domain": "com.bumble"
                    }
                }
            ],
            "message_id": 1,
            "message_type": 2,
            "version": 1,
            "is_background": False
        }
        return self.call('?SERVER_APP_STARTUP', data)

    def update_session(self):
        data = {
            "$gpb": "badoo.bma.BadooMessage",
            "body": [
                {
                    "message_type": 199,
                    "server_update_session": {
                        "hotpanel_session_id": "1c8ca36d-2634-4fc2-bb87-634778f6902b"
                    }
                }
            ],
            "message_id": 7,
            "message_type": 199,
            "version": 1,
            "is_background": False
        }
        return self.call('?SERVER_UPDATE_SESSION', data)

    def confirm_screen_story(self):
        data = {
            "$gpb": "badoo.bma.BadooMessage",
            "body": [
                {
                    "message_type": 688,
                    "server_confirm_screen_story": {
                        "screen_story_id": "bumble_web_pin_form|1:0282cbfa-cbfa-fad9-d9f1-f14fbe817bfb"
                    }
                }
            ],
            "message_id": 20,
            "message_type": 688,
            "version": 1,
            "is_background": False
        }

        return self.call('?SERVER_CONFIRM_SCREEN_STORY', data, 688)

    def validate_phone(self):
        data = {
            "$gpb": "badoo.bma.BadooMessage",
            "body": [
                {
                    "message_type": 640,
                    "server_validate_phone_number": {
                        "phone_prefix": "+33",
                        "phone": self.phone,
                        "context": 203
                    }
                }
            ],
            "message_id": 9,
            "message_type": 640,
            "version": 1,
            "is_background": False
        }
        return self.call('?SERVER_VALIDATE_PHONE_NUMBER', data)

    def submit_phone(self):
        data = {
            "$gpb": "badoo.bma.BadooMessage",
            "body": [
                {
                    "message_type": 678,
                    "server_submit_phone_number": {
                        "phone_prefix": "+33",
                        "screen_context": {
                            "screen": 23
                        },
                        "phone": self.phone,
                        "context": 203
                    }
                }
            ],
            "message_id": 11,
            "message_type": 678,
            "version": 1,
            "is_background": False
        }
        return self.call('?SERVER_SUBMIT_PHONE_NUMBER', data)

    def check_phone_pin(self, pin_code):
        data = {
            "$gpb": "badoo.bma.BadooMessage",
            "body": [
                {
                    "message_type": 680,
                    "server_check_phone_pin": {
                        "pin": pin_code,
                        "screen_context": {
                            "screen": 25
                        }
                    }
                }
            ],
            "message_id": 23,
            "message_type": 680,
            "version": 1,
            "is_background": False
        }
        return self.call('?CHECK_PHONE_PIN', data, 680)

    @need_login
    def iter_encounters(self):
        data = {
            "$gpb": "badoo.bma.BadooMessage",
            "body": [
                {
                    "message_type": 81,
                    "server_get_encounters": {
                        "number": 10,
                        "context": 1,
                        "user_field_filter": {
                            "projection": [
                                210,
                                370,
                                200,
                                230,
                                490,
                                540,
                                530,
                                560,
                                291,
                                732,
                                890,
                                930,
                                662,
                                570,
                                380,
                                493,
                                1140,
                                1150,
                                1160,
                                1161
                            ],
                            "request_albums": [
                                {
                                    "album_type": 7
                                },
                                {
                                    "album_type": 12,
                                    "external_provider": 12,
                                    "count": 8
                                }
                            ],
                            "game_mode": 0,
                            "request_music_services": {
                                "top_artists_limit": 8,
                                "supported_services": [
                                    29
                                ],
                                "preview_image_size": {
                                    "width": 120,
                                    "height": 120
                                }
                            }
                        }
                    }
                }
            ],
            "message_id": 30,
            "message_type": 81,
            "version": 1,
            "is_background": False
        }
        r = self.call('?SERVER_GET_ENCOUNTERS', data)
        if 'no_more_search_results' in r['body'][0]:
            self.logger.warning('No results :(')
            return

        for user in r['body'][0]['client_encounters']['results']:
            yield user['user']

    @need_login
    def like_user(self, user, like=True):
        data = {
            "$gpb": "badoo.bma.BadooMessage",
            "body": [
                {
                    "message_type": 80,
                    "server_encounters_vote": {
                        "person_id": user['user_id'],
                        "vote": 2 if like else 3,
                        "vote_source": 1,
                        "game_mode": 0
                    }
                }
            ],
            "message_type": 80,
            "version": 1,
            "is_background": False
        }
        self.call('?SERVER_ENCOUNTERS_VOTE', data)

    @need_login
    def get_users_list(self):
        data = {
            "$gpb": "badoo.bma.BadooMessage",
            "body": [
                {
                    "message_type": 245,
                    "server_get_user_list": {
                        "user_field_filter": {
                            "projection": [
                                200,
                                210,
                                340,
                                230,
                                640,
                                580,
                                300,
                                860,
                                280,
                                590,
                                591,
                                250,
                                700,
                                762,
                                592,
                                880,
                                582,
                                930,
                                585,
                                583,
                                305,
                                330,
                                763,
                                1423,
                                584,
                                1262,
                                911,
                                912
                            ]
                        },
                        "preferred_count": 50,
                        "folder_id": 0,
                        "filter": [
                            3
                        ],
                        "section_requests": [
                            {
                                "section_id": "2"
                            }
                        ]
                    }
                }
            ],
            "message_id": 61,
            "message_type": 245,
            "version": 1,
            "is_background": False
        }
        r = self.call('?SERVER_GET_USER_LIST', data)

        for user in r['body'][0]['client_user_list']['section'][-1]['users']:
            yield user

    @need_login
    def get_my_user(self):
        if not self.my_user:
            self.my_user = self.get_user(self.my_id)

        return self.my_user

    @need_login
    def get_user(self, user_id):
        data = {
            "$gpb": "badoo.bma.BadooMessage",
            "body": [
                {
                    "message_type": 403,
                    "server_get_user": {
                        "user_id": user_id,
                        "user_field_filter": {
                            "game_mode": 0,
                            "projection": [
                                200,
                                340,
                                230,
                                310,
                                370,
                                762,
                                890,
                                493,
                                530,
                                540,
                                291,
                                490,
                                1160,
                                1161,
                                210,
                                380
                            ],
                            "request_music_services": {
                                "top_artists_limit": 10,
                                "supported_services": [
                                    29
                                ]
                            },
                            "request_albums": [
                                {
                                    "person_id": user_id,
                                    "album_type": 2,
                                    "offset": 1
                                },
                                {
                                    "person_id": user_id,
                                    "album_type": 12,
                                    "external_provider": 12
                                }
                            ]
                        },
                        "client_source": 10
                    }
                }
            ],
            "message_id": 69,
            "message_type": 403,
            "version": 1,
            "is_background": False
        }

        r = self.call('?SERVER_GET_USER', data)

        return r['body'][0]['user']

    @need_login
    def get_user_messages(self, user_id):
        data = {
            "$gpb": "badoo.bma.BadooMessage",
            "body": [
                {
                    "message_type": 102,
                    "server_open_chat": {
                        "user_field_filter": {
                            "projection": [
                                200,
                                210,
                                340,
                                230,
                                640,
                                580,
                                300,
                                860,
                                280,
                                590,
                                591,
                                250,
                                700,
                                762,
                                592,
                                880,
                                582,
                                930,
                                585,
                                583,
                                305,
                                330,
                                763,
                                1423,
                                584,
                                1262,
                                911,
                                912
                            ],
                            "request_albums": [
                                {
                                    "count": 10,
                                    "offset": 1,
                                    "album_type": 2,
                                    "photo_request": {
                                        "return_preview_url": True,
                                        "return_large_url": True
                                    }
                                }
                            ]
                        },
                        "chat_instance_id": user_id,
                        "message_count": 50
                    }
                }
            ],
            "message_id": 68,
            "message_type": 102,
            "version": 1,
            "is_background": False
        }

        r = self.call('?SERVER_OPEN_CHAT', data)

        try:
            return r['body'][0]['client_open_chat']['chat_messages']
        except KeyError:
            return []

    @need_login
    def send_message(self, user_id, message):
        data = {
            "$gpb": "badoo.bma.BadooMessage",
            "body": [
                {
                    "message_type": 104,
                    "chat_message": {
                        "mssg": message,
                        "message_type": 1,
                        "uid": str(int(time.time()*1000)),
                        "from_person_id": self.my_id,
                        "to_person_id": user_id,
                        "read": False
                    }
                }
            ],
            "message_id": 101,
            "message_type": 104,
            "version": 1,
            "is_background": False
        }

        self.call('?SERVER_SEND_CHAT_MESSAGE', data)
