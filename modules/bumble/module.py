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

from datetime import datetime
from time import sleep, time
import json
import html

import openai

from woob.capabilities.dating import CapDating, Optimization
from woob.capabilities.messages import Thread, Message, CapMessages, CapMessagesPost
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import Value, ValueTransient
from woob.tools.log import getLogger

from .browser import BumbleBrowser


__all__ = ['BumbleModule']


class ProfilesWalker(Optimization):
    def __init__(self, sched, storage, browser, city: str):
        self._sched = sched
        self._storage = storage
        self._browser = browser
        self._city = city
        self._logger = getLogger('walker', browser.logger)

        self._view_cron = None

    def start(self):
        self._view_cron = self._sched.schedule(1, self.view_profile)
        return True

    def stop(self):
        self._sched.cancel(self._view_cron)
        self._view_cron = None
        return True

    def set_config(self, params):
        pass

    def is_running(self):
        return self._view_cron is not None

    def view_profile(self):
        next_try = 30
        try:
            for user in self._browser.iter_encounters():
                if not self._city or self._city in user['distance_long']:
                    like = True
                    self._logger.info('Like %s' % user['name'])
                else:
                    like = False
                    self._logger.info('Unlike %s (%s)' % (user['name'], user['distance_long']))

                if self._browser.like_user(user, like):
                    self._logger.info('Match with %s' % user['name'])

                sleep(3)

        finally:
            if self._view_cron is not None:
                self._view_cron = self._sched.schedule(next_try, self.view_profile)


class AutoResponder(Optimization):
    def __init__(self, sched, browser, chatgpt_key):
        self._sched = sched
        self._browser = browser
        self._cron = None
        self._logger = getLogger('openai', browser.logger)
        openai.api_key = chatgpt_key

    def start(self):
        self._cron = self._sched.schedule(1, self.check_messages)
        return True

    def stop(self):
        self._sched.cancel(self._cron)
        self._cron = None
        return True

    def set_config(self, params):
        pass

    def is_running(self):
        return self._cron is not None

    def build_user_profile(self, user):
        data = {}

        if user['gender'] == 2:
            data['Sexe'] = 'Femme'
        else:
            data['Sexe'] = 'Homme'

        data['Age'] = f"{user['age']} ans"
        if 'hometown' in user and 'city' in user['hometown']:
            data['Localisation'] = user['hometown']['city']['name']
        if 'primary_text' in user['profile_summary']:
            data['Profession'] = user['profile_summary']['primary_text']
        for field in user['profile_fields']:
            if field['display_value']:
                data[field['name']] = field['display_value']

        return data


    def build_prompt(self, my_user, other_user, messages):
        my_name = self._browser.my_name

        my_profile_text = self.build_user_profile(my_user)
        my_profile_text = '\n\n'.join(f"{key}:\n{value}" for key, value in self.build_user_profile(my_user).items())
        my_name = self._browser.my_name
        other_profile_text = '\n\n'.join(f"{key}:\n{value}" for key, value in self.build_user_profile(other_user).items())
        other_name = other_user['name']

        messages_text = ''
        for message in messages:
            sender = other_user['name'] if message['from_person_id'] == other_user['user_id'] else self._browser.my_name
            content=html.unescape(message['mssg'])

            messages_text += f'{sender}:\n"{content}"\n\n'

        content = f"""
Je suis {my_name}, un utilisateur d'un site de rencontre nommé Bumble.

Mon profil est le suivant :

{my_profile_text}

{other_name} est quelqu'un dont le profil est le suivant :

{other_profile_text}

Voici la liste des derniers messages :

{messages_text}

Peux-tu me donner une proposition d'une réponse que je pourrais lui apporter, dans un style humoristique un peu sarcastique, sous format JSON ?
"""

        return content

    def chatgpt(self, prompt):
        r = openai.ChatCompletion.create(model='gpt-3.5-turbo', messages=[{'role': 'user', 'content': prompt}])
        content = r['choices'][0]['message']['content']
        msg = json.loads(content)
        return msg['message']


    def check_messages(self):
        next_try = 90
        try:
            for user in self._browser.get_users_list():
                if user['is_match'] is False or (user['connection_status_indicator'] == 0 and user['unread_messages_count'] == 0):
                    continue

                sleep(5)
                messages = self._browser.get_user_messages(user['user_id'])

                # Only answer to the first message.
                if len(messages) == 0 or self._browser.my_id in {m['from_person_id'] for m in messages}:
                    continue

                if messages[0]['date_created'] > time() + 60:
                    continue

                prompt = self.build_prompt(self._browser.get_my_user(), self._browser.get_user(user['user_id']), messages)

                self._logger.debug('Built prompt:\n%s', prompt)
                message_to_post = self.chatgpt(prompt)
                self._browser.send_message(user['user_id'], message_to_post)
                self._logger.info("Sent message to %s: %s", user['name'], message_to_post)

        finally:
            if self._cron is not None:
                self._cron = self._sched.schedule(next_try, self.check_messages)


class BumbleModule(Module, CapDating, CapMessages, CapMessagesPost):
    NAME = 'bumble'
    DESCRIPTION = 'Bumble dating mobile application'
    MAINTAINER = 'Roger Philibert'
    EMAIL = 'roger.philibert@gmail.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.6'
    CONFIG = BackendConfig(Value('phone',  label='Phone number'),
                           Value('city', label='City where to like people (optional)', required=False),
                           Value('chatgpt_key', label='ChatGPT API Key (optional)', required=False),
                           ValueTransient('pincode')
                           )
    STORAGE = {'contacts': {}}

    BROWSER = BumbleBrowser

    def create_default_browser(self):
        return self.create_browser(self.config)

    # ---- CapDating methods -----------------------

    def init_optimizations(self):
        self.browser.do_login()
        self.add_optimization('PROFILE_WALKER', ProfilesWalker(self.woob.scheduler, self.storage, self.browser, self.config['city'].get()))
        if self.config['chatgpt_key'].get():
            self.add_optimization('AUTO_RESPONDER', AutoResponder(self.woob.scheduler, self.browser, self.config['chatgpt_key'].get()))


    # ---- CapMessages methods -----------------------
    def iter_threads(self):
        for user in self.browser.get_users_list():
            if user['is_match'] is False:
                continue

            t = Thread(user['user_id'])
            t.flags = Thread.IS_DISCUSSION
            t.title = f"Discussion with {user['name']}"
            yield t

    def get_thread(self, id):
        user = self.browser.get_user(id)

        if isinstance(id, Thread):
            thread = id
            id = thread.id
        else:
            thread = Thread(user['user_id'])
            thread.flags = Thread.IS_DISCUSSION
            thread.title = f"Discussion with {user['name']}"

        contact = self.storage.get('contacts', thread.id, default={'lastmsg': 0})

        for message in reversed(self.browser.get_user_messages(thread.id)):
            flags = 0
            if not contact['lastmsg'] or int(contact['lastmsg']) < int(message['uid']):
                flags = Message.IS_UNREAD

            msg = Message(
                thread=thread,
                id=message['uid'],
                title=thread.title,
                sender=user['name'] if message['from_person_id'] == user['user_id'] else self.browser.my_name,
                receivers=[user['name'] if message['from_person_id'] != user['user_id'] else self.browser.my_name],
                date=datetime.fromtimestamp(message['date_created']),
                content=html.unescape(message['mssg']),
                children=[],
                parent=None,
                signature='',
                flags=flags
            )

            if thread.root:
                thread.root.parent = msg
                msg.children.append(thread.root)

            thread.root = msg

        return thread

    def set_message_read(self, message):
        contact = self.storage.get('contacts', message.thread.id, default={'lastmsg': 0})
        if int(contact['lastmsg']) < int(message.id):
            contact['lastmsg'] = int(message.id)
            self.storage.set('contacts', message.thread.id, contact)
            self.storage.save()

    # ---- CapMessagesPost methods ---------------------
    def post_message(self, message):
        self.browser.send_message(message.thread.id, message.content)
