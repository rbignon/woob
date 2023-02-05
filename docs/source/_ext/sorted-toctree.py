from sphinx.directives.other import TocTree


class SortedTocTree(TocTree):
    def parse_content(self, toctree):
        r = super().parse_content(toctree)
        print('coucou', toctree['entries'])
        print('coucou2', toctree['includefiles'])
        toctree['entries'] = list(sorted(toctree['entries']))
        toctree['includefiles'] = list(sorted(toctree['includefiles']))
        return r


def setup(app):
    app.add_directive("sorted-toctree", SortedTocTree)

    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
