# Troubleshooting

## Python is not recognized

Install Python 3.10 or newer and enable its PATH option. On Windows try `py backend/local_server.py`; on macOS/Linux try `python3 backend/local_server.py`. Run the command from the extracted project root, not from inside the frontend directory.

## Browser shows a file path or the interface cannot call the API

Open `http://127.0.0.1:8000` after starting the server. Do not double click `index.html`. Keep the terminal running. To stop, press Ctrl+C. If port 8000 is in use, run `python backend/local_server.py --port 8080` and open port 8080 instead.

## Where is the administrator setup key?

Locally, it is printed on first startup and stored in `data/setup-key.txt`. AWS CloudShell prints it after deployment and stores it in the private deployment state file. In the manual console route, use the key you supplied as the CloudFormation parameter. Setup only appears while no administrator has been created. An existing administrator signs in normally.

Do not delete your local `data/` folder merely to recover access: it contains all local demo records. For a deliberate complete reset, stop the server and rename `data` to a backup folder before restarting.

## Doctor or invoice form says no eligible appointments

Patients create appointments. Doctors can add records and complete visits only once the scheduled time arrives. The invoice form excludes cancelled appointments and appointments that already have an invoice. The project issues one invoice per appointment.

## Booking rejected

Choose a real calendar date in the future, within 180 days, between 09:00 and 17:30 IST, with minutes 00 or 30. A booked doctor or patient cannot take another appointment at the same time. An administrator or the owning patient can reschedule; a doctor cannot reschedule. Cancelled and completed appointments cannot be changed.

## Too many login attempts

Wait five minutes before trying again for that email address. Each email has a shared attempt window across application instances.

## CloudShell says boto3 is missing

Ensure you are in the AWS Console's CloudShell, rather than your local terminal or an unrelated hosted shell. Local use does not need boto3. Use the manual CloudFormation console route if your managed CloudShell image lacks the AWS Python SDK.

## AWS AccessDenied / role creation rejected

Use the learner lab's existing Lambda execution role via `--role-arn`, if available. It must allow DynamoDB and log operations, and you must be allowed to pass it to Lambda. Check that the lab is active and the requested region is permitted. Do not create access keys or install npm to fix an IAM permission error; those do not grant additional permissions.

## CloudFormation ROLLBACK_COMPLETE

Open the stack's Events tab and read the earliest resource failure. Fix the permission, service restriction or parameter first. Delete the failed stack, then retry the deployment. A stack in ROLLBACK_COMPLETE cannot be updated normally. The script prints failed resource events when its waiter fails. An error before stack creation may leave the private artifact bucket; delete it when abandoning the deployment.

## AWS Internal Server Error

Open CloudWatch Logs → `/aws/lambda/careflow-hospital-app` for the error. Confirm TABLE_NAME and ADMIN_SETUP_KEY exist in Lambda environment variables and the execution role can access the DynamoDB table. Upload the entire included Lambda ZIP, not just one Python file. The handler is `lambda_function.lambda_handler`. Use the default API Gateway stage created by the template; do not add a named stage prefix to AppUrl.

## Local records missing on AWS

Local SQLite and AWS DynamoDB are separate databases. Create the demo accounts and appointments on the hosted URL too. Local data is deliberately not uploaded during deployment.

## Changed code is not visible

Run the deployment script again from the changed project directory. For manual deployments, rebuild `deployment/careflow-lambda.zip`, upload it under a new S3 object key and update the stack parameter. The project requires no frontend npm build.
