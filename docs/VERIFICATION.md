# Verification

Verified on 24 October 2026.

| Check | Result |
| --- | --- |
| Standard library functional suite | 16 tests passed |
| Simultaneous booking requests | Exactly one winner; second request receives conflict |
| Reschedule transaction conflict | Original appointment and locks preserved |
| Cancellation and slot reuse | Passed |
| Role and appointment ownership restrictions | Passed |
| Administrator bootstrap, duplicate email and logout | Passed |
| Consultation records and completion timing | Passed |
| Invoice amount precision and payment permissions | Passed |
| JSON, cross site and session cookie checks | Passed |
| DynamoDB adapter using Moto mock AWS | Registration, sessions, doctor creation, booking, conflict, reschedule, cancellation and expiry attributes passed |
| Packaged Lambda ZIP | Extracted handler imported; health, HTML, CSS and JavaScript routes passed with mock AWS |
| CloudFormation template | cfn-lint validation passed with no findings |
| Frontend JavaScript syntax | Passed Node syntax validation in the build environment |
| Chromium browser workflow | Administrator setup, doctor creation, sign out, patient registration, booking and rescheduling passed |
| Browser runtime errors | None during the tested workflow |
| Responsive layout | Inspected at 1440 px desktop and 390 px mobile; no document width overflow |
| Final ZIP integrity | Checked before delivery |

Run the included dependency free functional tests from the project root:

```text
python -m unittest discover -s tests -v
```

The DynamoDB request shape subcheck runs when botocore is available; local tests otherwise still run without it. Moto, cfn-lint, Chromium and build environment tooling are not application dependencies and are not shipped in the project. You do not need to install them to run CareFlow.

No live AWS stack was created during these checks. Mock AWS tests do not verify your account's IAM policies, lab restrictions, quotas or actual service availability. The project still needs deployment in your own AWS account using the included instructions. No hosted URL or AWS deployment screenshots are claimed.
