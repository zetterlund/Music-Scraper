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


SONG_COUNT = 20


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
    # page = html.fromstring(response.text)

    pattern = re.compile('"videoRenderer":{"videoId":"(.*?)"')
    m = re.search(pattern, response.text)
    videoURL = m.group(1)

    # videoURL = page.xpath('//ol[@class="item-section"]//li/div[contains(@class, "yt-lockup-video")]')[0].xpath('.//h3[contains(@class, "yt-lockup-title")]//a/@href')[0]
    # videoURL = re.sub(r'^.*?watch\?v=(.*)', r'\1', videoURL)

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
        if stream['format'] == 'audio only (tiny)' and stream['extension'] == 'm4a':
            downloadURL = stream['url']
            return downloadURL

    # If proper stream not found in response, return error
    return "Stream not found"


def downloadSong(song, downloadURL, ):
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

    r = requests.get(downloadURL, allow_redirects=True)
    open(os.path.join(directory, fileName), 'wb').write(r.content)

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
            return "dub success"

        except Exception as e:
            debug.error("Failed to convert song from m4a to mp3.  Filename: {}.  Error: {}".format(fileName, e))
            return "dub failure"

        finally:
            os.remove(os.path.join(directory, fileName))
            time.sleep(0.5)



def getSong(index):
    try:
        debug.debug("Beginning getSong for index: {}".format(index))

        song = recordList[index]

        song['query'] = getQuery(song)
        song['videoURL'] = getVideoURL(song['query'])

        downloadURL = getDownloadURL(song)
        if downloadURL == "API Failed":
            song['outcome'] = "api-failure"
            debug.warning("API failed to retrieve song for index: {}".format(index))
        if downloadURL == "Stream not found":
            song['outcome'] = "api-failure"
            debug.warning("Failed to find proper stream for song at index: {}".format(index))
        else:
            result = downloadSong(song, downloadURL)
            if result == "dub failure":
                song['outcome'] = "dub-failure"
            else:
                song['outcome'] = "success"

    except Exception as e:
        song['outcome'] = "error"
        debug.error("Problem encountered in 'getSong' function.\nError: {}\nSong: {}\n".format(e, song))

    finally:
        with lock:
            recordList[index] = song
        debug.debug("Finished getSong for index: {}.  Outcome: {}".format(index, song['outcome']))



def runThreads(iterable, max_workers=3, exec_func=getSong):
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(exec_func, iterable)



def getSongIndices(recordList):
    song_indices = list() # Create empty list to fill with the songs that we decide worthy of capturing

    # Shuffled list of all indexes in recordList
    all_indices = list(range(len(recordList)))
    random.shuffle(all_indices)

    for i in all_indices:
        song = recordList[i]

        # Check if the song is eligible to be scraped
        if song.get('outcome', None) in ['error', 'success']:
            debug.debug('Skipping song because of its existing outcome.  song[outcome] = {}'.format(song.get('outcome', None)))
            continue
        if song.get('stationName', None) == 'KCRW':
            debug.debug('Skipping song as station is KCRW')
            continue

        # Since the song is eligible, add it to 'song_indices'
        song_indices.append(i)

        # Check that 'song_indices' isn't longer than our SONG_COUNT constant
        if len(song_indices) >= SONG_COUNT:
            break

    return song_indices



''' Read API credentials '''
config = configparser.ConfigParser()
config.read('credentials.ini')
apiHost = str(config['credentials']['host'])
apiKey = str(config['credentials']['key'])



if __name__ == '__main__':

    # Set up debugger file
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler = logging.FileHandler(os.path.join(os.getcwd(), "debug.log"))
    handler.setFormatter(formatter)
    debug = logging.getLogger('debug')
    debug.setLevel('DEBUG')
    debug.addHandler(handler)
    debug.addHandler(logging.StreamHandler())

    # Define locks for threading
    os_lock = threading.Lock()
    dub_lock = threading.Lock()
    lock = threading.Lock()

    # Load record list
    with open('songRecords.json') as json_file:
        recordList = json.load(json_file)

    # Select songs to capture
    song_indices = getSongIndices(recordList)

    # Execute getSong function within ThreadPool
    debug.debug("Now beginning to execute ThreadPool")
    runThreads(iterable=song_indices, max_workers=3, exec_func=getSong)

    # Save record list
    debug.debug("All finished.  Now saving the updated recordList.")
    with open('songRecords.json', 'w') as outfile:
        json.dump(recordList, outfile)
