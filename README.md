# Resident Archive

https://residentarchive.com / [@residentarchive](https://twitter.com/ResidentArchive)

Resident Archive keeps the entire [RA](https://ra.co) music collection in sync with Spotify:

## Features

Automatically builds yearly playlists from:

   - up to 1 million existing RA songs,
      - https://ra.co/tracks/1
      - https://ra.co/tracks/1000000
      - ...
   - daily new RA songs ([discontinued](https://twitter.com/ResidentArchive/status/1349521888607936512))
   - previously unreleased RA songs that were released on Spotify today.

## How it works

3 CRON jobs running on AWS Lambda:

 - λ1 [`from-residentadvisor`](functions/from-residentadvisor/)
 - λ2 [`to-spotify`](functions/to-spotify/)
 - λ3 [`to-twitter`](functions/to-twitter/)

