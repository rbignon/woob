from woob.browser import URL, PagesBrowser

from .pages.index import IndexPage
from .pages.torrents import TorrentPage, TorrentsPage


__all__ = ["TorrentzBrowser"]


class TorrentzBrowser(PagesBrowser):
    BASEURL = "https://torrentz2.eu/"

    index_page = URL(r"/$", IndexPage)
    torrents_page = URL(r"/search\?f=(?P<query>.+)", TorrentsPage)
    torrent_page = URL(r"/(?P<hash>[0-9a-f]+)", TorrentPage)

    def home(self):
        return self.index_page.go()

    def iter_torrents(self, pattern):
        self.torrents_page.go(query=pattern)
        return self.page.iter_torrents()

    def get_torrent(self, id):
        self.torrent_page.go(hash=id)
        return self.page.get_torrent()

    def get_torrent_file(self, id):
        self.torrent_page.go(hash=id)
        return self.page.get_torrent_file()
