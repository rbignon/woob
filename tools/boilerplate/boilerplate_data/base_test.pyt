<%inherit file="layout.pyt"/>
from woob.tools.test import BackendTest


class ${r.classname}Test(BackendTest):
    MODULE = '${r.name}'
