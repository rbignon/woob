# -*- coding: utf-8 -*-

# Copyright(C) 2018      Vincent A
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

from __future__ import unicode_literals

from woob.capabilities.captcha import ImageCaptchaJob
from woob.tools.test import BackendTest


class AnticaptchaTest(BackendTest):
    MODULE = 'anticaptcha'

    def test_image(self):
        url = 'https://upload.wikimedia.org/wikipedia/commons/b/b6/Modern-captcha.jpg'
        data = self.backend.browser.open(url).content

        job = ImageCaptchaJob()
        job.image = data
        self.assertTrue(self.backend.solve_catpcha_blocking(job))
        self.assertEqual(job.solution, 'following finding')
