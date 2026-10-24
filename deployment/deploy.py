import argparse
import hashlib
import json
import re
import secrets
import sys
from pathlib import Path
from build import build

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description='Deploy CareFlow from AWS CloudShell. No local npm, pip or SAM required.')
    parser.add_argument('--region', default='ap-south-1')
    parser.add_argument('--stack', default='careflow-hospital')
    parser.add_argument('--role-arn', default='', help='Existing Lambda execution role ARN, useful for AWS Academy LabRole.')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]{0,49}', args.stack):
        parser.error('Stack name must start with a letter and contain at most 50 letters, digits or hyphens.')
    try:
        import boto3
        from botocore.exceptions import ClientError, WaiterError
    except ImportError:
        sys.exit('Run this deployment command in AWS CloudShell, which provides boto3. Local use only needs backend/local_server.py.')
    session = boto3.Session(region_name=args.region)
    account = session.client('sts').get_caller_identity()['Account']
    cfn, s3 = session.client('cloudformation'), session.client('s3')
    bucket = f'careflow-{account}-{args.region}-{hashlib.sha256(args.stack.encode()).hexdigest()[:10]}'
    state_path = ROOT / 'deployment' / f'{args.stack}-state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    try:
        cfn.describe_stacks(StackName=args.stack)
        exists = True
    except ClientError as exc:
        if exc.response['Error']['Code'] == 'ValidationError' and 'does not exist' in str(exc):
            exists = False
        else:
            raise
    if exists:
        print('Updating existing stack. The current administrator setup key is preserved.')
    else:
        state['setupKey'] = secrets.token_urlsafe(32)
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as exc:
        if exc.response['Error']['Code'] in ('404', 'NoSuchBucket', 'NotFound'):
            create = {'Bucket': bucket}
            if args.region != 'us-east-1':
                create['CreateBucketConfiguration'] = {'LocationConstraint': args.region}
            s3.create_bucket(**create)
        else:
            raise
    s3.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration={
        'BlockPublicAcls': True, 'IgnorePublicAcls': True, 'BlockPublicPolicy': True, 'RestrictPublicBuckets': True})
    s3.put_bucket_encryption(Bucket=bucket, ServerSideEncryptionConfiguration={'Rules': [{'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}]})
    package = build()
    key = 'releases/' + hashlib.sha256(package.read_bytes()).hexdigest() + '.zip'
    s3.upload_file(str(package), bucket, key)
    params = [{'ParameterKey': 'CodeBucket', 'ParameterValue': bucket}, {'ParameterKey': 'CodeKey', 'ParameterValue': key},
              {'ParameterKey': 'ExistingLambdaRoleArn', 'ParameterValue': args.role_arn}]
    params.append({'ParameterKey': 'AdminSetupKey', **({'UsePreviousValue': True} if exists else {'ParameterValue': state['setupKey']})})
    state.update(stack=args.stack, region=args.region, bucket=bucket, account=account)
    state_path.write_text(json.dumps(state, indent=2), encoding='utf-8')
    state_path.chmod(0o600)
    request = {'StackName': args.stack, 'TemplateBody': (ROOT / 'deployment' / 'cloudformation.json').read_text(),
               'Parameters': params, 'Capabilities': ['CAPABILITY_IAM']}
    try:
        if exists:
            cfn.update_stack(**request)
        else:
            cfn.create_stack(**request)
    except ClientError as exc:
        if 'No updates are to be performed' in str(exc):
            print('Stack already up to date.')
        else:
            raise
    else:
        print('Waiting for CloudFormation. This usually takes a few minutes.')
        try:
            cfn.get_waiter('stack_update_complete' if exists else 'stack_create_complete').wait(StackName=args.stack)
        except WaiterError:
            for event in cfn.describe_stack_events(StackName=args.stack)['StackEvents']:
                if 'FAILED' in event['ResourceStatus']:
                    print(event['LogicalResourceId'] + ': ' + event.get('ResourceStatusReason', 'Unknown failure'))
            sys.exit('Deployment failed. Inspect CloudFormation Events; see docs/TROUBLESHOOTING.md. State file retained for cleanup.')
    stack = cfn.describe_stacks(StackName=args.stack)['Stacks'][0]
    if stack['StackStatus'] not in ('CREATE_COMPLETE', 'UPDATE_COMPLETE'):
        sys.exit('Stack is not ready: ' + stack['StackStatus'])
    print('\nCareFlow deployed successfully.')
    for output in stack.get('Outputs', []):
        print(output['OutputKey'] + ': ' + output['OutputValue'])
    if state.get('setupKey'):
        print('Administrator setup key: ' + state['setupKey'])
    print('Open AppUrl, choose Set up the administrator, and enter the setup key.')
    print('Keep the state file private. Do not commit it to GitHub.')


if __name__ == '__main__':
    main()
