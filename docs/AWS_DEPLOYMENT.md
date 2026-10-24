# AWS deployment: no npm and no CloudFront

## What you need

An AWS account or AWS Academy learner lab with an active session and access to Lambda, API Gateway HTTP APIs, DynamoDB, S3, CloudWatch Logs and CloudFormation. Standard accounts need permission to create an IAM execution role. Learner labs can instead pass an existing LabRole. No services are deployed merely by downloading this ZIP.

## Recommended route: AWS CloudShell

1. Sign in to AWS. If using AWS Academy, start your lab and open its AWS Console first.
2. Select **Mumbai, ap-south-1** if your account/lab permits it. The region passed to the script must be a region your lab supports.
3. Open **CloudShell**, using the terminal icon in the console header. This is the AWS browser terminal. You do not need to install anything on your own computer.
4. In CloudShell choose **Actions → Upload file** and upload `CareFlow_AWS_Final.zip`.
5. Run:

   ```bash
   unzip CareFlow_AWS_Final.zip
   cd CareFlow_AWS_Final
   python3 deployment/deploy.py --region ap-south-1
   ```

6. Wait for `CareFlow deployed successfully`. The script prints **AppUrl**, **TableName**, **FunctionName** and a unique **administrator setup key**.
7. Open AppUrl. It is an HTTPS API Gateway URL that also serves the website. Click **Set up the administrator** and use the setup key to create an administrator account. Public patient registration never grants administrator access.
8. Add doctors in Administration, register a patient account, then make a booking.
9. Use the screenshot/demo checklist in `DEMO_GUIDE.md`.

### AWS Academy / existing LabRole

If the lab denies IAM role creation, copy the ARN of the existing Lambda execution role, often named `LabRole`, from IAM → Roles or the learner lab instructions. Then deploy with:

```bash
python3 deployment/deploy.py --region ap-south-1 --role-arn arn:aws:iam::123456789012:role/LabRole
```

Replace the example ARN with your own account's actual role ARN. The template skips IAM role creation when an existing ARN is supplied. That role must trust `lambda.amazonaws.com`, permit DynamoDB GetItem, Scan, PutItem and DeleteItem on the project's table, and allow CloudWatch log writes. DynamoDB transactional writes authorize against the individual item actions. You also need `iam:PassRole` for that role. Lab restrictions cannot be bypassed by this project; ask the lab administrator if required services or permissions are disabled.

If the first stack failed and is in `ROLLBACK_COMPLETE`, delete the failed CloudFormation stack before retrying. Keep the artifact bucket or let the script reuse it. Do not run a fresh create while the failed stack still exists.

## What the deployment script does

1. Builds the Python/HTML/CSS/JavaScript deployment ZIP.
2. Creates a private, encrypted S3 artifact bucket in the chosen region.
3. Uploads the ZIP with a content based object name.
4. Creates or updates the CloudFormation stack.
5. Waits for stack completion and prints the website URL.

The stack includes one DynamoDB table, a Python 3.12 Lambda, its execution role unless supplied, a CloudWatch log group with seven day retention, an API Gateway HTTP API, its default route and stage, and permission for API Gateway to invoke Lambda. It does not create CloudFront, EC2, RDS or MongoDB. It does not enable a Lambda function URL.

The API route uses payload format 2.0. Browser session cookies are returned through the Lambda response's `cookies` field. On AWS they are HttpOnly, Secure and SameSite=Strict.

## Updating the deployed project

Copy changed project files into CloudShell and run the same deployment command with the same stack name, region and role ARN. The code package is rebuilt. The DynamoDB table and original administrator setup key remain in place. Updates that replace the database resource or stack are not part of the normal code update flow.

The script saves a private `deployment/careflow-hospital-state.json` for the deployment key and artifact bucket details. Do not publish that file, the local `data/` folder or real credentials to GitHub. For subsequent code updates with an existing role, pass the same `--role-arn` again.

## Manual console alternative

If CloudShell is unavailable but your AWS Console permits resource creation:

1. Create a **private S3 bucket** in your chosen AWS region. Keep Block all public access enabled.
2. Upload the included **`deployment/careflow-lambda.zip`** to that bucket. Note the exact object key, such as `careflow-lambda.zip`.
3. Open CloudFormation → Create stack → With new resources → Upload a template file. Select **`deployment/cloudformation.json`**.
4. Set stack name to `careflow-hospital`. Set `CodeBucket` to the bucket name and `CodeKey` to the exact uploaded object key.
5. Set `AdminSetupKey` to a randomly generated secret of at least 32 characters. You can generate one locally without dependencies:

   ```text
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

6. Leave `ExistingLambdaRoleArn` blank for a standard account that can create roles. For a lab, supply the existing LabRole ARN. Acknowledge IAM resource creation when requested.
7. Create the stack. When status reaches CREATE_COMPLETE, open the **Outputs → AppUrl** URL.
8. Set up the administrator using your chosen key. Do not manually configure a separate API Gateway or Lambda URL; the template already does that.

For manual console updates after changing the source, build the Lambda ZIP using `python deployment/build.py`, upload it under a **new S3 object key**, then update the stack with that key. Replacing bytes at the same S3 key alone does not tell CloudFormation to update Lambda.

## Deleting the project after the review

**This permanently deletes the DynamoDB database and its records.** In CloudShell, from the project folder:

```bash
python3 deployment/cleanup.py --region ap-south-1 --yes-delete-data
```

Use the original `--stack` name if you chose a custom name. The script deletes the CloudFormation stack, then empties and deletes its artifact bucket using the deployment state file. If using the manual console route, delete the stack in CloudFormation, then separately empty and delete your private S3 bucket. Check that stack deletion succeeded before closing the lab.

## Official references

* Python Lambda runtimes and included SDK: https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html
* API Gateway HTTP API Lambda payload and cookies: https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html
* DynamoDB transaction API: https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html
* CloudFormation Lambda resource: https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-lambda-function.html
