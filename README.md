## Automatic Music Library Expander

One evening, while driving home from work, I tuned into KUTX 98.9 FM and my ears were greeted by a wonderful song: "Sisyphus" by Andrew Bird.

Not wanting to miss out on all the other great songs KUTX plays, I decided to build a program to directly add their songs to my computer.

**Every day, this program downloads a random selection of 250 songs that were played on KUTX at some point between 2014-2019.**

Here's an overview of the script:

1. A one-time script is initially run which makes a series of Requests to KUTX's online Playlist API.  This compiles the JSON file of all songs played between 2014-2019.  (20mb file)
1. The program selects 250 random songs from the JSON list, and initiates multiple threads to begin process of gathering songs.
1. Each thread iterates through the list, grabbing a single song.
1. The song information is converted and encoded into a YouTube search query URL that is likely to contain the target song in the first search result.  (For example, "Sisyphus" by Andrew Bird becomes "https://www.youtube.com/results?search_query=andrew+bird+-+sisyphus")
1. Request is made to YouTube and the first result's video URL is saved
1. Video URL is sent through RapidAPI service which converts the video to audio
1. Audio file is downloaded and converted to mp3 through Mutagen
1. ID3 tags are added to the audio file

Then I can conveniently just download the mp3s from my server.  The results have been good - it's tedious work to slog through the bad music, but I keep ~ 10% of the songs in my library and it's really helped me expand my music collection.