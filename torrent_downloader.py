import libtorrent as lt
import time
import logging
import os

class TorrentDownloader(object):

    def __init__(self, **kwargs):
        self.ses = lt.session()
        self.ses.listen_on(6881, 6891)

        torrent_file = kwargs.get("torrent_file")
        save_path = kwargs.get("save_path")

        e = lt.bdecode(open(torrent_file, "rb").read())
        info = lt.torrent_info(e)
        params = {
            'ti': info,
            'save_path' : save_path,
            'storage_mode' : lt.storage_mode_t.storage_mode_sparse,
            'paused' : False,
            'auto_managed' : True,
            'duplicate_is_error' : True
        }

        try:
            resume_path = ''.join([save_path, info.name(), '.fastresume'])
            params['resume_data'] = open(os.path.join(resume_path, 'rb')).read()
        except:
            pass
        self.handle = self.ses.add_torrent(params)
        logging.info("Starting %s" % self.handle.name())

    def download(self):
        while self.handle.status().state != lt.torrent_status.seeding:
            s = self.handle.status()
            state_str = ['queued', 'checking', 'downloading metadata',
                         'downloading', 'finished', 'seeding', 'allocating', 'checking_resume_data']
            print '%.2f%% complete (down: %.1f kb/s up: %.1f kb/s peers: %d) %s' % \
                (s.progress * 100, s.download_rate / 1000, s.upload_rate / 1000, s.num_peers, state_str[s.state])
            time.sleep(5)









