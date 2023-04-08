<%inherit file="layout.pyt"/>
from woob.tools.backend import Module

from .browser import ${r.classname}Browser


__all__ = ['${r.classname}Module']


class ${r.classname}Module(Module):
    NAME = '${r.name}'
    DESCRIPTION = '${r.description}'
    MAINTAINER = '${r.author}'
    EMAIL = '${r.email}'
    LICENSE = 'LGPLv3+'

    BROWSER = ${r.classname}Browser
