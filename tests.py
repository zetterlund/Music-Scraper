import unittest
from music_scraper import *

lock = threading.Lock()
os_lock = threading.Lock()

def test_threads_exec(i):
    with lock:
        time.sleep(0.5)

class TestScript(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open('songRecords.json') as json_file:
            cls.recordList = json.load(json_file)

    @classmethod
    def tearDownClass(cls):
        pass

    def test_record_list_length(self):
        self.assertTrue(len(self.recordList) > 50000)

    def test_threading(self):
        import time
        from datetime import datetime
        start = datetime.now()
        runThreads(range(5), max_workers=2, exec_func=test_threads_exec)
        end = datetime.now()
        self.assertTrue((end-start).total_seconds() > 2.5)

class TestScraper(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open('songRecords.json') as json_file:
            cls.recordList = json.load(json_file)
        cls.song = None
        cls.downloadURL = None

    @classmethod
    def tearDownClass(cls):
        pass

    def test_api_service(self):
        song = self.recordList[46987]
        song['query'] = getQuery(song)
        song['videoURL'] = getVideoURL(song['query'])
        downloadURL = getDownloadURL(song)
        self.assertNotIn(downloadURL, [None, 'API Failed', 'Stream not found'])
        self.song = song
        self.downloadURL = getDownloadURL(song)

    def testdownloader(self):
        result = downloadSong(self.song, self.downloadURL)
        if result == "dub failure":
            song['outcome'] = "dub-failure"
        else:
            song['outcome'] = "success"

    # Not currently working properly as tests are interdependent and need to be executed in the correct order (i.e. test api service, and then test downloader)



if __name__ == '__main__':
    unittest.main()
