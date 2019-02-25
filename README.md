# RA-tracks

Up-to-date Spotify playlists for [residentadvisor.net](https://residentadvisor.net)'s community-made music library.

## λ1 – From Resident Advisor

 - Gets and stores all track names from https://residentadvisor.net/tracks
 - Triggers λ2 for each entry

Triggered by `CRON(1 minute)` and once all songs are found, `CRON(1 hour)`.

## λ2 – To Spotify

 - Indefinitely search for stored songs on Spotify
 - Create yearly playlists and add songs to them

Triggered by:

 - `CRON(5 minutes)`
 - λ1
