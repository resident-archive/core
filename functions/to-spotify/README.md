### Generate a Spotify token

Before running locally or deploying this, use `token_gen.py` to generate and store a Spotify token into DynamoDB.

### Run locally

    virtualenv ./.venv
    source ./.venv/bin/activate
    pip install -r requirements.txt
    python token_gen.py
    python main.py
    deactivate

### Build and deploy

Fill in `./functions/to-spotify/env.json` with `SPOTIPY_CLIENT_ID` and `SPOTIPY_CLIENT_SECRET`, and then:

    apex build
    apex deploy to-spotify --region eu-west-1 -ldebug --env-file ./functions/to-spotify/env.json

### AWS prerequesites

 - All from λ1
 - DynamoDB tables:
    - CursorsTable
        - name: `ra_cursors`
        - partition key: `name` (string)
    - CursorsTable
        - name: `ra_playlists`
        - partition key: `year` (string)
        - sort_key" `num` (decimal)
