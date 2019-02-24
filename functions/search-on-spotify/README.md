### Generate a Spotify token

Before running locally or deploying this, a first token should be generated.
`token_gen.py` can be used to generate a new one.
It will open a new browser window and save the token in the `.cache-{userud}` file.

### Run locally

    virtualenv ./.venv
    source ./.venv/bin/activate
    pip install -r requirements.txt
    python token_gen.py
    python main.py
    deactivate

### Build and deploy

    apex build
    apex deploy search-on-spotify --region eu-west-1

### AWS prerequesites

 - All from λ1
 - DynamoDB table:
    - name: `ra_cursors`
    - partition key: `name` (string)
