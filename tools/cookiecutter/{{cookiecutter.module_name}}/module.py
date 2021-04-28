# -*- coding: utf-8 -*-

# Copyright(C) {{cookiecutter.year}} {{cookiecutter.full_name}}
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

# flake8: compatible

from __future__ import unicode_literals

from woob.capabilities.{{cookiecutter.capability | replace('Cap', '') | lower}} import {{cookiecutter.capability}}
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword

from .browser import {{cookiecutter.class_prefix}}Browser


__all__ = ["{{cookiecutter.class_prefix}}Module"]


class {{cookiecutter.class_prefix}}Module(Module, {{cookiecutter.capability}}):
    NAME = "{{cookiecutter.module_name}}"
    DESCRIPTION = "{{cookiecutter.site_name}}"
    MAINTAINER = "{{cookiecutter.full_name}}"
    EMAIL = "{{cookiecutter.email}}"
    LICENSE = "LGPLv3+"
    VERSION = "3.1"

    BROWSER = {{cookiecutter.class_prefix}}Browser

    CONFIG = BackendConfig(
        ValueBackendPassword("login", label="Username", masked=False),
        ValueBackendPassword("password", label="Password"),
    )

    def create_default_browser(self):
        return self.create_browser(
            self.config["login"].get(),
            self.config["password"].get()
        )

    def iter_something(self):
        return self.browser.iter_something()
