import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

import json
import decimal
import os
import time

from bs4 import BeautifulSoup
import urlparse
import requests


def url_at_index(index):
    return 'https://www.residentadvisor.net/tracks/' + str(index)


def stringified_page(url):
    '''
    Request a webpage
    '''
    r = requests.get(url)

    if r.status_code == 200:
        for hist in r.history:
            if hist.status_code != 200:
                raise Exception(r.status_code)
        return r.text
    else:
        raise Exception(r.status_code)


def get_song_with_index(index):
    url = url_at_index(index)
    try:
        content = stringified_page(url)
    except Exception:
        os.environ['last'] = str(index + 1)
        raise
    page = BeautifulSoup(content, 'html.parser')
    return page.find('h1').getText()


# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)


def handler(event, context):
    dynamodb = boto3.resource("dynamodb", region_name='eu-west-1')
    table = dynamodb.Table('tracks')

    current_id = int(event.get('last') or os.environ.get('last'))
    now = int(time.time())
    print current_id
    ra_name = get_song_with_index(current_id)
    print ra_name
    response = table.put_item(
       Item={
            'id': current_id,
            'added': now,
            'ra_name': ra_name
        }
    )

    os.environ['last'] = str(current_id + 1)
    print("PutItem succeeded:")
    return json.dumps(response, indent=4, cls=DecimalEncoder)


if __name__ == "__main__":
    print handler({'last': 1}, {})
