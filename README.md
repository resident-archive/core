# RA-tracks

Up-to-date Spotify playlists for [residentadvisor.net](https://residentadvisor.net)'s community-made music library.

## λ1 – Fetch ResidentAdvisor tracks

 - Gets all track names from https://residentadvisor.net/tracks to DynamoDB
 - Triggers λ2 for each entry

## λ2 – Search on Spotify

 - Search for old and new songs on Spotify
 - Triggers λ3 when a Spotify song is found

## λ3 – To Spotify Playlists

 - Adds a Spotify song to the Spotify playlist
 - Create playlist for each year
