# -*- coding: utf-8 -*-

# Copyright(C) 2021 woob project
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

from woob.capabilities.base import empty, NotLoaded
from woob.capabilities.messages import Thread


def _first_non_empty(*args, default=NotLoaded):
    for arg in args:
        if not empty(arg):
            return arg
    return default


def build_linear_thread(messages, thread=None, title=None):
    if thread is None:
        thread = Thread()
        thread.flags = Thread.IS_DISCUSSION

    it = iter(messages)

    root = next(it)
    root.thread = thread
    thread.root = root

    thread.title = _first_non_empty(thread.title, root.title, title)
    root.title = _first_non_empty(root.title, thread.title, title)

    # empty string by default, can't use _first_non_empty
    thread.id = thread.id or root.id or NotLoaded

    thread.url = thread.url or root.url

    if empty(thread.date):
        thread.date = root.date

    root.children = []

    for message in it:
        message.thread = thread
        if empty(message.title) and not empty(root.title):
            message.title = f"Re: {root.title}"
        root.children.append(message)

    return thread
