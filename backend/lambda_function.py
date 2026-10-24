import os
from app import Application
from storage import DynamoStore

application = Application(DynamoStore(os.environ['TABLE_NAME']), os.environ['ADMIN_SETUP_KEY'], mode='aws')


def lambda_handler(event, context):
    return application.handle(event)
