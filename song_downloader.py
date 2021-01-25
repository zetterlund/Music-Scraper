#!/usr/bin/env python
# coding: utf-8

# In[ ]:


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
from datetime import date, datetime
from mutagen.easyid3 import EasyID3
from pydub import AudioSegment
from sqlalchemy.sql.expression import func


# In[ ]:


# Read credentials

config = configparser.ConfigParser()
config.read('credentials.ini')
apiHost = str(config['credentials']['host'])
apiKey = str(config['credentials']['key'])
dbURL = str(config['credentials']['dburl'])


# In[ ]:


# Connect to database

from sqlalchemy import create_engine
engine = create_engine(dbURL)

from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)

session = Session()


# In[ ]:


# Define database object mapping

from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

from sqlalchemy import Column, Integer, String, Boolean
class Song(Base):
    __tablename__ = 'songs'
    
    id = Column(Integer, primary_key=True)
    track = Column(String)
    artist = Column(String)
    slug = Column(String)
    collection = Column(String)
    duration = Column(Integer)
    station = Column(String)
    program = Column(String)    
    downloaded = Column(Boolean, default=False)
    datePlayed = Column(Integer)
    genre = Column(String)
    query = Column(String)
    videoURL = Column(String)
    outcome = Column(String)
    status = Column(String)
    
    def __repr__(self):
        return "<Song(track='%s', artist='%s', station='%s')" % (self.track, self.artist, self.station)


# In[ ]:


# Configure global variables

SUCCESSFUL_SONGS = 0
SONG_COUNT_TO_DOWNLOAD = 50
THREADS = []


# In[ ]:


# Attach search query to song object

def getQuery(song):
    queryList = []
    if song.artist:
        artist_query = urllib.parse.quote_plus(song.artist)
        queryList.append(artist_query)
    if song.track:
        track_query = urllib.parse.quote_plus(song.track)
        queryList.append(track_query)
    query = '+'.join(queryList)
    song.query = query
    return song


# In[ ]:


# Attach video URL to song object

def getVideoURL(song):
    response = requests.get('https://www.youtube.com/results?search_query={}'.format(song.query))
    pattern = re.compile('"videoRenderer":{"videoId":"(.*?)"')
    m = re.search(pattern, response.text)
    videoURL = m.group(1)
    song.videoURL = videoURL
    return song


# In[ ]:


def getDownloadURL(song):
    youtubeURL = 'https://www.youtube.com/watch?v={}'.format(song.videoURL)
    youtubeURL = urllib.parse.quote_plus(youtubeURL)
    apiURL = 'https://getvideo.p.rapidapi.com/?url={}'.format(youtubeURL)
    apiHeaders = {
        "X-RapidAPI-Host": apiHost,
        "X-RapidAPI-Key": apiKey
    }
    response = requests.get(apiURL, headers=apiHeaders)
    response = json.loads(response.text)
    
    # There are several streams in the response; just grab the first one
    # (API has not been working recently; use try/except...)
    try:
        song.downloadURL = response['streams'][0]['url']
    except Exception as e:
        debug.warning("getDownloadURL failed for song with ID {}.  Exception: {}".format(song.id, e))
        song.status = "api_error"
    finally:
        return song


# In[ ]:


def downloadSong(song):
    fileName = "{} - {} - {}".format(song.artist, song.track, song.station)
    fileName = re.sub(r'[^A-Za-z0-9\s\-]', '', fileName)
    fileName += ".m4a"
    
    dateString = datetime.date(datetime.now()).strftime('%Y-%m-%d')
    directory = os.path.join(os.getcwd(), 'downloads', 'archive', dateString)
    filePath = os.path.join(directory, fileName)
    with os_lock:
        if not os.path.exists(directory):
            os.makedirs(directory)

    r = requests.get(song.downloadURL, allow_redirects=True)
    with open(filePath, 'wb') as file:
        file.write(r.content)

    # Set audio file metadata
    with dub_lock:
        time.sleep(0.2)
        try:
            dub_audio = AudioSegment.from_file(filePath, "m4a")
            newFileName = re.sub(r'm4a$', r'mp3', fileName)
            dub_audio.export(os.path.join(directory, newFileName), "mp3")
            song.downloaded = True

            # (Specify default value of '' because value of None is not accepted)
            audio = EasyID3(os.path.join(directory, newFileName))
            audio["title"] = song.track if song.track else ''
            audio["artist"] = song.artist if song.artist else ''
            audio["album"] = song.collection if song.collection else ''
            audio["compilation"] = song.program if song.program else ''
            audio["genre"] = ";".join([song.station, 'Scraped']) if song.station else "Scraped"
            audio.save()

            song.status = "success"
            return song

        except Exception as e:
            debug.error("Failed to convert song from m4a to mp3 for song with ID {}.  Exception: {}".format(song.id, e))
            song.status = "dub_error"
            return song

        finally:
            with os_lock:
                os.remove(filePath)
                time.sleep(0.2)


# In[ ]:


def getSong():
    global SUCCESSFUL_SONGS
    
    # Select one random song from database
    with db_lock:
        
        # Select a random station
        station = random.choice(['KBPA', 'W249AR', 'WQNQHD2', 'KUTX'])
        
        song = session.query(Song).filter(Song.downloaded == False, Song.status == None, Song.station == station).order_by(func.random()).first()

        # (If no song is found, cancel the process)
        if not song:
            debug.warning("No song found when looking in station {}.".format(station))
            with lock:
                SUCCESSFUL_SONGS += 1
            return

        song.status = 'processing'

    try:
        getQuery(song)
        getVideoURL(song)    
        getDownloadURL(song)
        
        if getattr(song, 'downloadURL', None):
            downloadSong(song)
            if song.status == "success":
                with lock:
                    SUCCESSFUL_SONGS += 1   

    except Exception as e:
        debug.error("getSong failed somewhere for song with ID {}.  Exception: {}".format(song.id, e))
        song.status = "uncaught_error"


# In[ ]:


def runThread():
    global SUCCESSFUL_SONGS
    global SONG_COUNT_TO_DOWNLOAD
    global THREADS
    
    THREADS.append(threading.current_thread().name)
    
    while (SUCCESSFUL_SONGS + len(THREADS)) <= SONG_COUNT_TO_DOWNLOAD:
        getSong()
        time.sleep(0.5)
        
    THREADS.remove(threading.current_thread().name)


# In[ ]:


def initializeThreads():
    t1 = threading.Thread(target=runThread, name='t1')
    t2 = threading.Thread(target=runThread, name='t2')
    t3 = threading.Thread(target=runThread, name='t3')

    t1.start()
    t2.start()
    t3.start()

    t1.join()
    t2.join() 
    t3.join()


# In[ ]:


if __name__ == '__main__':

    # Set up debugger file
    formatter = logging.Formatter('%(asctime)s:%(funcName)s:%(levelname)s - %(message)s')
    handler = logging.FileHandler(os.path.join(os.getcwd(), "song_downloader_debug.log"))
    handler.setFormatter(formatter)
    debug = logging.getLogger('debug')
    debug.setLevel('DEBUG')
    debug.addHandler(handler)
    debug.addHandler(logging.StreamHandler())

    # Define locks for threading
    db_lock = threading.Lock()
    os_lock = threading.Lock()
    dub_lock = threading.Lock()
    lock = threading.Lock()

    # Initialize threads
    initializeThreads()
    
    # Save the results in the database
    session.commit()

    debug.info("Finished run") 


# In[ ]:


session.close()

