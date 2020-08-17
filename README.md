# Resident Archive

https://residentarchive.com

Resident Archive keeps the entire [RA](https://residentadvisor.net) music collection in sync with Spotify:

## Features

Automatically builds yearly playlists from:

   - up to 1M existing RA songs,
      - https://www.residentadvisor.net/tracks/1
      - https://www.residentadvisor.net/tracks/940000
      - ...
   - daily new RA songs,
      - https://www.residentadvisor.net/tracks
   - previously unreleased RA songs that were released on Spotify today.

## How it works

2 CRON jobs running on AWS Lambda:

 - λ1 [`from-residentadvisor`](functions/from-residentadvisor/)
 - λ2 [`to-spotify`](functions/to-spotify/)
 - λ3 [`to-social`](functions/to-social/)

