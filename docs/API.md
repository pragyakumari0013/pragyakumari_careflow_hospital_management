# API reference

Base path `/api`. Bodies and responses are JSON. Errors return `{"error":"message"}`. The browser uses the HttpOnly `careflow_session` cookie; tokens are not stored in JavaScript storage. Mutation requests require `Content-Type: application/json`, including empty requests `{}`.

| Method | Endpoint | Access / body |
| --- | --- | --- |
| GET | `/health` | Public; runtime storage label and timezone |
| GET | `/setup` | Public; `needsAdmin` boolean |
| POST | `/setup` | One time; `name,email,password,setupKey` |
| POST | `/register` | Public patient registration; `name,email,password` |
| POST | `/login` | Public; `email,password`; sets session cookie |
| POST | `/logout` | Authenticated; revokes current session |
| GET | `/me` | Authenticated; own public user profile and storage mode |
| GET | `/dashboard` | Authenticated; scoped counts and recent appointments |
| GET | `/doctors` | Authenticated; doctor directory |
| POST | `/doctors` | Administrator; `name,email,password,department` |
| GET | `/users` | Administrator; public profiles, never password hashes |
| GET | `/appointments` | Scoped by role and ownership |
| POST | `/appointments` | Patient; `doctorId,when,reason` |
| POST | `/appointments/{id}/cancel` | Owning patient, assigned doctor or administrator |
| POST | `/appointments/{id}/reschedule` | Owning patient or administrator; `when` |
| POST | `/appointments/{id}/complete` | Assigned doctor or administrator; after scheduled time |
| GET | `/records` | Scoped by visible appointments |
| POST | `/records` | Assigned doctor or administrator; `appointmentId,diagnosis,prescription`; after scheduled time |
| GET | `/invoices` | Owning patient or administrator |
| POST | `/invoices` | Administrator; `appointmentId,amount,description`; amount is a decimal string |
| POST | `/invoices/{id}/paid` | Administrator; records manual payment |

`when` format: `YYYY-MM-DDTHH:mm`, interpreted as Asia/Kolkata, not the caller's device timezone. IDs are generated UUID hex strings. Common response statuses: 200 success, 201 resource created, 400 invalid input, 401 no valid session, 403 forbidden, 404 absent endpoint/item, 409 conflicting state or unique key, 413 request too large, 415 unsupported content type, 429 login limit, 500 server error.
