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


def lambda_handler(event, context):
    dynamodb = boto3.resource("dynamodb", region_name='eu-west-1')
    table = dynamodb.Table('tracks')

    response = table.put_item(
       Item={
            'id': int(os.environ['last']) + 1,
            'added': int(time.time())
        }
    )

    os.environ['last'] = str(int(os.environ['last']) + 1)
    print("PutItem succeeded:")
    return json.dumps(response, indent=4, cls=DecimalEncoder)
