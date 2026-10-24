# CareFlow Hospital Management System

A complete academic hospital management project with a Python backend and a plain HTML, CSS and browser JavaScript interface. No Node.js, npm, React, pip packages or database installation is required on your computer.

## Start on your computer

1. Extract the ZIP and open a terminal inside `CareFlow_AWS_Final`.
2. Check Python: `python --version` (Python 3.10 or newer).
3. Run:

   ```text
   python backend/local_server.py
   ```

4. Open **http://127.0.0.1:8000**. Keep the terminal running.
5. Copy the administrator setup key printed in the terminal. Click **Set up the administrator** and create your administrator account.
6. In **Administration**, add a doctor with a fictional email and initial password.
7. Sign out. Use **Patient registration** to create a patient account and book a visit.
8. Sign out and sign in with the doctor's credentials to view assigned appointments.

On macOS/Linux use `python3` if `python` is unavailable. On Windows, `py backend/local_server.py` is another option. You can also double click `START_WINDOWS.bat`. To use another port: `python backend/local_server.py --port 8080`.

**JavaScript runs in the browser only. You never install npm.** Do not open `frontend/index.html` directly; the Python server serves the interface and API together.

## Deploy on AWS

Open **[docs/AWS_DEPLOYMENT.md](docs/AWS_DEPLOYMENT.md)**. The recommended route is AWS CloudShell:

```text
python3 deployment/deploy.py --region ap-south-1
```

Run that command inside the extracted project in CloudShell, not in your local terminal. The deployment script uses the AWS Python SDK already provided there. There is no local AWS CLI, SAM, Docker or npm installation requirement. A prebuilt `deployment/careflow-lambda.zip` and the complete CloudFormation template are included.

Architecture: browser → API Gateway HTTP API → Python Lambda → DynamoDB. The same Lambda serves the web interface and API on one HTTPS URL. S3 privately stores the deployment package; S3 does not host the website. CloudFront is not used.

## Included features

| Area | Implemented behavior |
| --- | --- |
| Accounts | Protected administrator setup, patient registration, doctor account creation, sign in, server side sessions and sign out |
| Access control | Administrator sees all appointments; doctors see assigned visits; patients see their own visits and records |
| Dashboard | Role specific appointment counts and recent visits |
| Care team | Doctor directory with departments |
| Appointments | Book, cancel, reschedule and complete visits; validate dates; prevent simultaneous doctor or patient bookings |
| Consultation records | Assigned doctors and administrators add consultation summaries and instructions after the scheduled time; patients read their own records |
| Billing | Administrator issues one invoice per appointment and records manual payment; patients view their invoices |
| Storage | Persistent SQLite locally; DynamoDB on AWS |
| Deployment | Python packaging and deployment scripts, CloudFormation, cleanup script and troubleshooting guide |

All appointment slots are **30 minutes**, **09:00 to 17:30 IST**, within the next **180 days**. A future appointment cannot be completed and cannot receive a consultation record before its scheduled time. Invoices use integer paise to avoid floating point rounding errors. Invoices are manual accounting records; this project does not process actual payments.

## Folder guide

```text
CareFlow_AWS_Final/
  backend/                  Python application, storage adapters, local server and Lambda handler
  frontend/                 HTML, CSS and browser JavaScript; no build step
  deployment/               Ready Lambda ZIP, CloudFormation and deployment/cleanup scripts
  docs/                     Deployment, architecture, API, demo guide and troubleshooting
  tests/                    Functional and authorization tests
  START_WINDOWS.bat         Windows launcher
  start.sh                  macOS/Linux launcher
  README.md                 Start here
```

## Verification

Run `python -m unittest discover -s tests -v`. The functional tests use a disposable SQLite database and Python's standard library. They do not require AWS credentials or change your local application data. See `docs/VERIFICATION.md` for what was and was not tested.

## Project scope

This is an academic demonstration with fictional data, not a production hospital service. Features such as password recovery, email verification, staff onboarding automation, appointment reminders, patient file uploads, inventory, pharmacy, insurance, online payments and regulatory compliance are outside this project. Consultation records are append only in the interface. Accounts are not editable or deletable through the interface. There is no password change screen; use fictional credentials only.

DynamoDB reads use paginated scans for a small demonstration dataset. The booking locks and state changes use conditional transactions. A production service should use indexed access patterns, comprehensive audit trails, recovery controls and a separately reviewed identity system.

AWS resources may incur charges. Delete the demonstration when finished using `docs/AWS_DEPLOYMENT.md`. Local and AWS databases are independent; deployment does not migrate the SQLite database.
