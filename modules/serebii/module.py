# -*- coding: utf-8 -*-

# Copyright(C) 2019-2020 Célande Adrien
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

from __future__ import unicode_literals


from woob.tools.backend import Module
from woob.capabilities.rpg import CapRPG

from .browser import SerebiiBrowser


__all__ = ['SerebiiModule']


class SerebiiModule(Module, CapRPG):
    NAME = 'serebii'
    DESCRIPTION = 'This website collects any data about Pokémon games.'
    MAINTAINER = 'Célande Adrien'
    EMAIL = 'celande.adrien@gmail.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.2'

    BROWSER = SerebiiBrowser

    def iter_characters(self):
        return self.browser.iter_characters()

    def get_character(self, character_id):
        return self.browser.get_character(character_id)

    def iter_skills(self, skill_type=None):
        return self.browser.iter_skills(skill_type)

    def get_skill(self, skill_id):
        return self.browser.get_skill(skill_id)

    def iter_skill_set(self, character_id, skill_type=None):
        return self.browser.iter_skill_set(character_id, skill_type)

    def iter_character_classes(self):
        return self.browser.iter_character_classes()

    def get_character_class(self, class_id):
        """
        List weakness and strength of a Pokémon Type
        """
        return self.browser.get_character_class(class_id)

    def iter_collectable_items(self):
        return self.browser.iter_collectable_items()
