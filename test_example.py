# @ -*- coding: utf-8 -*-
import logging

import torrent_downloader as td
from torrent_parser import *

if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    credentials =  {
                'login_username': u'',
                'login_password': u'',
                'login': u'Вход'
            }
    engine = TorrentSearch(tracker_name = "rutracker", credentials=credentials)
    """
    credentials = {
                'username': u'',
                'password': u''
            }
    engine = TorrentSearch(tracker_name = "kinozal", credentials=credentials)
    """
    engine.logging_to_tracker()
    torrents = engine.search('Muse')
    i = 1
    for torrent in torrents:
        print "%d %s %s %s" % (i, torrent['name'], torrent['size'], torrent['link'])
        i += 1

    torrent = torrents[0]
    path = engine.download_torrent(torrent['link'])
    print path

    t = td.TorrentDownloader(torrent_file=path)
    t.download()
    os.remove(path)
