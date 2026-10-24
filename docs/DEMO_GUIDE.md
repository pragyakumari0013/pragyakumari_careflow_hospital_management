# Review demonstration and screenshot checklist

Use fictional names and addresses ending in `.test`, for example `admin@careflow.test`, `sana@careflow.test` and `patient@careflow.test`. Choose your own passwords with at least eight characters.

## Suggested demonstration

1. Show the sign in screen and the CareFlow branding.
2. Set up the administrator once using the key printed by the local server or AWS deployment script.
3. As administrator, create **Dr. Sana Rao**, department **Cardiology**. Show the doctor in the user directory.
4. Sign out and register patient **Aarav Mehta**. Open Care team and show the doctor card.
5. Open Appointments. Choose a future 30 minute slot between 09:00 and 17:30 IST. Book a visit with a fictional reason.
6. Show the patient dashboard and appointment status. Reschedule it, then show the updated time.
7. Register a second patient and try the same doctor and same slot. Show the conflict message.
8. Sign in as the doctor and show only assigned appointments. Adding consultation records and completing appointments requires the scheduled time to have arrived.
9. For a live consultation demonstration, book the next available half hour slot earlier in the day and wait until that time. The doctor can then write a consultation summary, add care instructions and mark the visit completed.
10. As administrator, issue an invoice for INR 450.99 and mark it paid to demonstrate manual payment recording.
11. Sign back in as the original patient and show that only their consultation records and invoices are visible.
12. Show AWS proof: CloudFormation Outputs, Lambda Python runtime, API Gateway HTTP API, DynamoDB items and CloudWatch logs.

Do not change system clocks or enter real health information. Demo records are ordinary records you create through the interface; the ZIP ships without a populated personal database.

## Screenshot deliverables to capture after deployment

| Screenshot | What it demonstrates |
| --- | --- |
| CareFlow sign in page with URL visible | Working hosted interface |
| Administrator dashboard and user directory | Staff creation and role based interface |
| Patient booking and appointment history | Appointment workflow |
| Duplicate slot message | Validation and transaction protection |
| Doctor consultation record | Clinical workflow, after the scheduled time |
| Patient records and invoice | Ownership restrictions and billing visibility |
| CloudFormation stack outputs | Stack deployed and AppUrl provisioned |
| Lambda configuration | Python 3.12 runtime and handler |
| API Gateway routes | Default HTTP API route integrated with Lambda |
| DynamoDB Explore table items | Persisted user and appointment records |
| CloudWatch log stream | Requests executed on AWS |

AWS deployment screenshots cannot be included before the project is deployed in your own AWS account.

## Short viva explanation

“The frontend is plain HTML, CSS and JavaScript executed by the browser. The backend is Python. Locally, Python serves the interface and stores records in SQLite. On AWS, API Gateway forwards both page requests and API requests to Lambda, and Lambda stores the same logical data in DynamoDB. We use a same origin API Gateway URL for the interface, so CloudFront is unnecessary. Conditional transactions prevent conflicting bookings. Every protected endpoint checks the logged in user's role and appointment ownership.”
