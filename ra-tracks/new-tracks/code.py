import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
import json
import decimal
import os
import time


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

    current_id = int(event['last'] or os.environ['last'])
    now = int(time.time())

    response = table.put_item(
       Item={
            'id': current_id,
            'added': now
        }
    )

    os.environ['last'] = str(current_id + 1)
    print("PutItem succeeded:")
    return json.dumps(response, indent=4, cls=DecimalEncoder)


if __name__ == "__main__":
    print handler({'last': 1}, {})
