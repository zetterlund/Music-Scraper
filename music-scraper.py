import concurrent.futures
import configparser
import json
import logging
import os
import random
import re
import requests
import threading
import time
import urllib.parse
from datetime import date, datetime, timedelta
from lxml import html
from mutagen.easyid3 import EasyID3
from pydub import AudioSegment
from urllib.request import urlretrieve

''' Set up debugger file '''
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler = logging.FileHandler(os.path.join(os.getcwd(), "debug.log"))
handler.setFormatter(formatter)
debug = logging.getLogger('debug')
debug.setLevel('DEBUG')
debug.addHandler(handler)
debug.addHandler(logging.StreamHandler())

''' Read API credentials '''
config = configparser.ConfigParser()
config.read('credentials.ini')
apiHost = str(config['credentials']['host'])
apiKey = str(config['credentials']['key'])


def getQuery(song):
    queryList = []
    if song['artistName'] is not None:
        artistName_query = urllib.parse.quote_plus(song['artistName'])
        queryList.append(artistName_query)
    if song['trackName'] is not None:
        trackName_query = urllib.parse.quote_plus(song['trackName'])
        queryList.append(trackName_query)
    query = '+'.join(queryList)
    return query


def getVideoURL(query):
    response = requests.get('https://www.youtube.com/results?search_query={}'.format(query))
    page = html.fromstring(response.text)
    videoURL = page.xpath('//ol[@class="item-section"]//li/div[contains(@class, "yt-lockup-video")]')[0].xpath('.//h3[contains(@class, "yt-lockup-title")]//a/@href')[0]
    videoURL = re.sub(r'^.*?watch\?v=(.*)', r'\1', videoURL)
    return videoURL


def getDownloadURL(song):
    youtubeURL = 'https://www.youtube.com/watch?v={}'.format(song['videoURL'])
    youtubeURL = urllib.parse.quote_plus(youtubeURL)
    apiURL = 'https://getvideo.p.rapidapi.com/?url={}'.format(youtubeURL)
    apiHeaders = {
        "X-RapidAPI-Host": apiHost,
        "X-RapidAPI-Key": apiKey
    }
    response = requests.get(apiURL, headers=apiHeaders)
    response = json.loads(response.text)

    downloadURL = None

    # API has not been working recently; check if error message returned
    status = response.get('message', None)
    if status == 'Failed to get info':
        return "API Failed"

    for stream in response['streams']:
        if stream['format'] == 'audio only' and stream['extension'] == 'm4a':
            downloadURL = stream['url']
            return downloadURL


def downloadSong(song, downloadURL):
    fileName = "{} - {} - {} - {}".format(song['artistName'], song['trackName'], song['datePlayed'], song['stationName'])
    fileName = re.sub(r'[^A-Za-z0-9\s\-]', '', fileName)
    fileName += ".m4a"

    with os_lock:
        try:
            date_string = datetime.date(datetime.now()).strftime('%Y-%m-%d')
            directory = os.path.join(os.getcwd(), 'downloads', 'archive', date_string)
            if not os.path.exists(directory):
                os.makedirs(directory)
        except Exception as e:
            debug.error("Failed to create directory.  Error: {}".format(e))

    urlretrieve(downloadURL, os.path.join(directory, fileName))

    # Set audio file metadata
    with dub_lock:
        time.sleep(0.5)
        try:
            dub_audio = AudioSegment.from_file(os.path.join(directory, fileName), "m4a")
            newFileName = re.sub(r'm4a$', r'mp3', fileName)
            dub_audio.export(os.path.join(directory, newFileName), "mp3")

            audio = EasyID3(os.path.join(directory, newFileName))
            audio["title"] = song["trackName"]
            audio["artist"] = song["artistName"]
            audio["album"] = song["collectionName"]
            audio["date"] = song["datePlayed"]
            audio["compilation"] = song["programName"]
            audio["genre"] = ";".join([song['stationName'], 'Scraped'])
            audio.save()

        except Exception as e:
            debug.error("Failed to convert song from m4a to mp3.  Filename: {}.  Error: {}".format(fileName, e))
        finally:
            os.remove(os.path.join(directory, fileName))
        time.sleep(0.5)


def getSong(name):
    try:
        debug.debug("Beginning getSong for index: {}".format(name))
        song = potentialSongs[name]
        song['query'] = getQuery(song)
        song['videoURL'] = getVideoURL(song['query'])
        downloadURL = getDownloadURL(song)
        if downloadURL == "API Failed":
            song['outcome'] = "api-failure"
            debug.warning("API failed to retrieve song for index: {}".format(name))
        else:
            downloadSong(song, downloadURL)
            song['outcome'] = "success"
    except Exception as e:
        song['outcome'] = "error"
        debug.error("Problem encountered in 'getSong' function.\nError: {}\nSong: {}\n".format(e, song))
    finally:
        with lock:
            recordList[name] = song
        debug.debug("Finished getSong for index: {}.  Outcome: {}".format(name, song['outcome']))



''' Old, unnecessary functions '''
# def songAlreadyExists(song):
#     with lock:
#         for record in recordList:
#             if record['outcome'] == "success":
#                 if record['artistName'] == song['artistName'] and record['trackName'] == song['trackName']:
#                     debug.info("Duplicate song found. Skipping song: Artist: {}. Track: {}.".format(record['artistName'], record['trackName']))
#                     return True
#                 elif record['videoURL'] == song['videoURL']:
#                     debug.info("Duplicate Video URL found. (song['videoURL']={}) Skipping song: Artist: {}. Track: {}.".format(song['videoURL'], record['artistName'], record['trackName']))
#                     return True
#                 elif record['id'] == song['id']:
#                     debug.info("Duplicate song ID found.  ID: {}".format(song['id']))
#                     return True
#         return False
# def getSongList():
#     headers = {
#         'Accept': 'application/json, text/javascript, */*; q=0.01',
#         'DNT': '1',
#         'Origin': 'https://kutx.org',
#         'Referer': 'https://kutx.org/playlist',
#         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.80 Safari/537.36'
#     }
#     response = requests.get("https://api.composer.nprstations.org/v1/widget/50ef24ebe1c8a1369593d032/day?date={}&format=json".format(scrapeDate))
#     page = json.loads(response.text)
#     songList = []
#     stationName = 'KUTX'
#     for program in page['onToday']:
#         programName = program['program']['name']
#         if program['playlist']:
#             for track in program['playlist']:
#                 try:
#                     song = dict()
#                     song['programName'] = programName
#                     song['collectionName'] = track.get('collectionName', 'NONE')
#                     song['trackName'] = track.get('trackName', 'NONE')
#                     song['artistName'] = track.get('artistName', 'NONE')
#                     song['id'] = track.get('_id', 'NONE')
#                     song['datePlayed'] = scrapeDate
#                     song['stationName'] = stationName
#                     songList.append(song)
#                 except Exception as e:
#                     debug.warning("Couldn't add song to songList.\nError: {}\nTrack: {}\n".format(e, track))
#     return songList


debug.debug("Setting scrape date ranges")
scrapeDate = date.today() - timedelta(days=2)
scrapeDate = scrapeDate.strftime('%Y-%m-%d')

# Define locks for threading
os_lock = threading.Lock()
dub_lock = threading.Lock()
lock = threading.Lock()



# Load record list
with open('songRecords.json') as json_file:
    recordList = json.load(json_file)

potentialSongs = recordList.copy()

# Remove songs that have already been captured or that we don't want
debug.debug("Removing songs we don't want to capture from list")
for song in list(potentialSongs):
    if song.get('outcome', None) not in [None, "api-failure"] or song['stationName'] == 'KCRW':
        potentialSongs.remove(song)

# Get list of indexes of random X songs to capture
debug.debug("Getting indexes of random X number of songs to capture")
song_indexes = set()
for i in range(150):
    song_indexes.add(random.randint(1,len(potentialSongs)))
song_indexes = list(song_indexes)

# Execute getSong functions
debug.debug("Now beginning to execute ThreadPool")
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    executor.map(getSong, song_indexes)

# Save record list
debug.debug("All finished.  Now saving the updated recordList.")
with open('songRecords.json', 'w') as outfile:
    json.dump(recordList, outfile)
