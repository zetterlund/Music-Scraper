#!/usr/bin/env python
# coding: utf-8

# In[ ]:


# Configure logging

import logging
logging.basicConfig(
    filename="station_api_scraper_debug.log",
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s - %(message)s',
)


# In[ ]:


# Read credentials

import configparser
config = configparser.ConfigParser()
config.read('credentials.ini')
dbURL = str(config['credentials']['dburl'])

import json
with open('URLs.json', 'r') as file:
    URLs = json.load(file)


# In[ ]:


# Connect to database

from sqlalchemy import create_engine
engine = create_engine(dbURL)

from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)


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


# If running the script for the first time, create the table within the database:

# Base.metadata.create_all(engine)


# In[ ]:


### Helper functions

# Convert time string to int of seconds
def convert_duration(duration):
    pattern = re.compile('(\d+)')
    groups = re.findall(pattern, duration)

    # Check that the duration appears to be a parsable value
    if (len(groups) not in [1,2,3]):
        return None

    seconds = 0
    for i, x in enumerate(groups):
        multiplier = 60 ** (len(groups) - 1 - i)
        seconds += int(x) * multiplier
    return seconds

# Combine track and artist in lowercase to check for uniqueness among variations in database
def convert_to_slug(track, artist):
    track = re.sub(r'[^a-zA-Z0-9]', '', track).lower()
    artist = re.sub(r'[^a-zA-Z0-9]', '', artist).lower()
    slug = track + artist
    return slug

# Converts date string to unix time
def convert_date(datePlayed):
    result = datetime.strptime(datePlayed, "%m-%d-%Y %H:%M:%S")
    
    # Convert to timestamp with hacky workaround to compensate for time zone
    result = int(result.timestamp() + 21600)
    
    return result


# In[ ]:


### GRAB SONGS

from lxml import etree
import requests
import json
import re
from datetime import datetime


# In[ ]:


session = Session()


# In[ ]:


### KBPA

page = requests.get(URLs['KBPA'])
root = etree.fromstring(page.content)

for s in root.xpath('//nowplaying-info[@type="track"]'):
    try:
        track = s.xpath('.//property[@name="cue_title"]')[0].text
        artist = s.xpath('.//property[@name="track_artist_name"]')[0].text
        slug = convert_to_slug(track, artist)

        # (Check if song is already in database and should be skipped)
        if session.query(Song).filter(Song.slug == slug).count():
            continue

        song = Song()
        song.track = track
        song.artist = artist
        song.slug = slug
        song.duration = convert_duration(s.xpath('.//property[@name="cue_time_duration"]')[0].text)
        song.program = s.xpath('.//property[@name="program_id"]')[0].text
        song.datePlayed = s.attrib.get('timestamp')
        song.station = 'KBPA'

        session.add(song)
        
    except Exception as e:
        logging.error('{} - {}'.format('KBPA', e))
    
session.commit()


# In[ ]:


### W249AR

page = requests.get(URLs['W249AR'])
content = json.loads(page.text)

for s in content['data']['sites']['find']['stream']['amp']['recentlyPlayed']['tracks']:
    try:
        track = s['title']
        artist = s['artist']['artistName']
        slug = convert_to_slug(track, artist)

        # (Check if song is already in database and should be skipped)
        if session.query(Song).filter(Song.slug == slug).count():
            continue    

        song = Song()
        song.track = track
        song.artist = artist
        song.slug = slug
        song.collection = s['albumName']
        song.duration = s['trackDuration']
        song.datePlayed = s['startTime']
        song.station = 'W249AR'

        session.add(song)
        
    except Exception as e:
        logging.error('{} - {}'.format('W249AR', e))    

session.commit()


# In[ ]:


### WQNQHD2

page = requests.get(URLs['WQNQHD2'])
content = json.loads(page.text)

for s in content['data']:
    try:
        track = s['title']
        artist = s['artist']
        slug = convert_to_slug(track, artist)

        # (Check if song is already in database and should be skipped)
        if session.query(Song).filter(Song.slug == slug).count():
            continue    

        song = Song()
        song.track = track
        song.artist = artist
        song.slug = slug
        song.collection = s['album']
        song.duration = s['trackDuration']
        song.datePlayed = s['startTime']
        song.station = 'WQNQHD2'

        session.add(song)
        
    except Exception as e:
        logging.error('{} - {}'.format('WQNQHD2', e))        

session.commit()


# In[ ]:


### KUTX

page = requests.get(URLs['KUTX'])
content = json.loads(page.text)

# Find the most recently-played (currently-playing) program playlist
playlist = None
for program in content['onToday']:
    if program.get('has_playlist', None):
        if program['playlist']:
            playlist = program['playlist']
        else:
            break

# Gather information for 20 most recent songs
for s in playlist[-20:]:
    try:
        track = s['trackName']
        artist = s['artistName']
        slug = convert_to_slug(track, artist)

        # (Check if song is already in database and should be skipped)
        if session.query(Song).filter(Song.slug == slug).count():
            continue

        song = Song()
        song.track = track
        song.artist = artist
        song.slug = slug
        song.collection = s.get('collectionName', None)
        song.duration = s['_duration'] / 1000
        song.datePlayed = convert_date(s['_start_time'])
        song.station = 'KUTX'

        session.add(song)
        
    except Exception as e:
        logging.error('{} - {}'.format('KUTX', e))        

session.commit()    


# In[ ]:


logging.info("Finished run")


# In[ ]:


session.close()

