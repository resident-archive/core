### Purpose

Fetches and stores all track names from `https://residentadvisor.net/tracks/{i}` where `i` goes from [`1`](https://residentadvisor.net/tracks/1) to +∞

### Run locally

    virtualenv ./.venv
    source ./.venv/bin/activate
    pip install -r requirements.txt
    python main.py
    deactivate

### Build and deploy

    apex build from-residentadvisor
    apex deploy from-residentadvisor --region eu-west-1

### AWS prerequesites

- DynamoDB table:
   - CursorsTable
     - name: `any_tracks`
        - partition key: `host` (string)
        - sort key: `id` (decimal)
 - IAM role:
    - name: `apex_lambda_function`
    - permissions: IAM, DynamoDB, Lambda
