import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Delete a CareFlow deployment and its database. Irreversible.')
    parser.add_argument('--stack', default='careflow-hospital')
    parser.add_argument('--region', default='ap-south-1')
    parser.add_argument('--yes-delete-data', action='store_true', help='Required: acknowledge permanent data deletion.')
    args = parser.parse_args()
    if not args.yes_delete_data:
        parser.error('Add --yes-delete-data only when you want to permanently delete this demo and all its data.')
    import boto3
    from botocore.exceptions import ClientError
    session = boto3.Session(region_name=args.region)
    cfn = session.client('cloudformation')
    try:
        cfn.delete_stack(StackName=args.stack)
        print('Deleting stack and DynamoDB table...')
        cfn.get_waiter('stack_delete_complete').wait(StackName=args.stack)
    except ClientError as exc:
        if 'does not exist' not in str(exc):
            raise
    state_path = Path(__file__).parent / f'{args.stack}-state.json'
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state['region'] != args.region:
            raise SystemExit('State file region differs. Artifact bucket was not touched.')
        current_account = session.client('sts').get_caller_identity()['Account']
        if state['account'] != current_account:
            raise SystemExit('State file account differs. Artifact bucket was not touched.')
        bucket = session.resource('s3').Bucket(state['bucket'])
        bucket.objects.all().delete()
        bucket.delete()
        state_path.unlink()
        print('Deployment artifact bucket deleted.')
    else:
        print('No deployment state found. Remove any CareFlow artifact bucket manually in S3.')
    print('Cleanup complete.')


if __name__ == '__main__':
    main()
