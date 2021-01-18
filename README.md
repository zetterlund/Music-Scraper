# Automatic Music Library Expander

One evening, while driving home from work, I tuned into KUTX 98.9 FM and my ears were greeted by a wonderful song: ["Sisyphus" by Andrew Bird](https://www.youtube.com/watch?v=5-KOZl5CLbU).

Not wanting to miss out on all the other great songs KUTX plays, I decided to build a program to directly add their songs to my computer.

---

Well, I built that program and it worked great. Then a year later I went back and improved it, adding some more radio stations to get music from.

Here's an overview of the program:

1. Every 30 minutes, "station_api_scraper.py" retrieves and saves metadata on the 20 most-recently played songs on each of the target radio stations.
1. Once a day, "song_downloader.py" downloads 50 random songs from the song list via a call to a remote API. Audio is converted to mp3 and ID3 tags are attached to the files.
1. I conveniently just download the mp3s from my server. The results have been good - it's tedious to slog through the bad music, but I keep ~ 10% of the songs in my library and it's really helped me expand my music collection.
