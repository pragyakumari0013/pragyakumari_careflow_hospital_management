import json
import sqlite3
from pathlib import Path


class Conflict(Exception):
    pass


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


class SQLiteStore:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS items (pk TEXT PRIMARY KEY, data TEXT NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=20)

    def get(self, key):
        with self.connect() as db:
            row = db.execute('SELECT data FROM items WHERE pk=?', (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, prefix):
        with self.connect() as db:
            rows = db.execute('SELECT data FROM items WHERE substr(pk,1,?)=?', (len(prefix), prefix)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def write(self, changes):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for key, new, expected in changes:
                row = db.execute('SELECT data FROM items WHERE pk=?', (key,)).fetchone()
                old = json.loads(row[0]) if row else None
                if old != expected:
                    raise Conflict('This item changed. Refresh and try again.')
                if new is None:
                    db.execute('DELETE FROM items WHERE pk=?', (key,))
                else:
                    db.execute('INSERT OR REPLACE INTO items VALUES (?,?)', (key, encode(new)))


class DynamoStore:
    def __init__(self, table):
        import boto3
        self.db = boto3.client('dynamodb')
        self.table = table

    def get(self, key):
        item = self.db.get_item(TableName=self.table, Key={'pk': {'S': key}}, ConsistentRead=True).get('Item')
        return json.loads(item['data']['S']) if item else None

    def list(self, prefix):
        result, start = [], None
        while True:
            args = dict(TableName=self.table, ConsistentRead=True,
                        FilterExpression='begins_with(pk, :p)', ExpressionAttributeValues={':p': {'S': prefix}})
            if start:
                args['ExclusiveStartKey'] = start
            response = self.db.scan(**args)
            result.extend(json.loads(item['data']['S']) for item in response.get('Items', []))
            start = response.get('LastEvaluatedKey')
            if not start:
                return result

    def write(self, changes):
        from botocore.exceptions import ClientError
        operations = []
        for key, new, expected in changes:
            args = {'TableName': self.table}
            if expected is None:
                args['ConditionExpression'] = 'attribute_not_exists(pk)'
            else:
                args.update(ConditionExpression='#d = :old', ExpressionAttributeNames={'#d': 'data'},
                            ExpressionAttributeValues={':old': {'S': encode(expected)}})
            if new is None:
                args['Key'] = {'pk': {'S': key}}
                operations.append({'Delete': args})
            else:
                args['Item'] = {'pk': {'S': key}, 'data': {'S': encode(new)}}
                expiry = new.get('expires', new.get('until'))
                if expiry is not None:
                    args['Item']['expires'] = {'N': str(int(expiry))}
                operations.append({'Put': args})
        try:
            self.db.transact_write_items(TransactItems=operations)
        except ClientError as exc:
            if exc.response['Error']['Code'] == 'TransactionCanceledException':
                reasons = exc.response.get('CancellationReasons', [])
                if any(r.get('Code') in ('ConditionalCheckFailed', 'TransactionConflict') for r in reasons):
                    raise Conflict('This item changed or the slot is already booked. Refresh and try again.') from exc
            raise
