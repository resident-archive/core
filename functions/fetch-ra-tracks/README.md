### Run locally

    virtualenv ./.venv
    source ./.venv/bin/activate
    pip install -r requirements.txt
    python main.py
    deactivate

### Build and deploy

    apex build
    apex deploy fetch-ra-tracks --region eu-west-1

### AWS prerequesites

 - DynamoDB table:
    - name: `any_tracks`
    - partition key: `host` (string)
    - sort key: `added` (number)
 - IAM role:
    - name: `apex_lambda_function`
    - permissions: IAM, DynamoDB, Lambda
