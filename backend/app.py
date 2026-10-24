import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit

from storage import Conflict

ROOT = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))
SESSION_SECONDS = 8 * 3600


class ApiError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


def require(condition, code, message):
    if not condition:
        raise ApiError(code, message)


def clean(value, maximum=200):
    require(isinstance(value, str), 400, 'Expected a text value.')
    value = value.strip()
    require(len(value) <= maximum, 400, f'Text must contain at most {maximum} characters.')
    return value


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
    return salt + ':' + digest


def matches(password, stored):
    return hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored)


def public(user):
    return {k: v for k, v in user.items() if k != 'passwordHash'}


class Application:
    def __init__(self, store, setup_key, mode='local'):
        self.store, self.setup_key, self.mode = store, setup_key, mode

    def response(self, status, payload, cookie=None, content_type='application/json; charset=utf-8'):
        headers = {'content-type': content_type, 'cache-control': 'no-store',
                   'x-content-type-options': 'nosniff', 'referrer-policy': 'same-origin',
                   'content-security-policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"}
        result = {'statusCode': status, 'headers': headers, 'body': json.dumps(payload) if content_type.startswith('application/json') else payload}
        if cookie:
            result['cookies'] = [cookie]
        return result

    def session_cookie(self, token='', max_age=SESSION_SECONDS):
        return f'careflow_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={max_age}' + ('; Secure' if self.mode == 'aws' else '')

    def session(self, event):
        headers = {k.lower(): v for k, v in event.get('headers', {}).items()}
        raw = '; '.join(event.get('cookies', [])) or headers.get('cookie', '')
        cookie = SimpleCookie()
        try:
            cookie.load(raw)
            token = cookie['careflow_session'].value if 'careflow_session' in cookie else ''
        except Exception:
            token = ''
        key = 'SESSION#' + hashlib.sha256(token.encode()).hexdigest()
        sess = self.store.get(key) if token else None
        require(sess and sess['expires'] > time.time(), 401, 'Please sign in again.')
        user = self.store.get('USER#' + sess['userId'])
        require(user is not None, 401, 'Account no longer exists.')
        return user, key, sess

    def create_session(self, user):
        token = secrets.token_urlsafe(32)
        key = 'SESSION#' + hashlib.sha256(token.encode()).hexdigest()
        self.store.write([(key, {'userId': user['id'], 'expires': int(time.time()) + SESSION_SECONDS}, None)])
        return self.response(200, {'user': public(user)}, self.session_cookie(token))

    def new_user(self, body, role):
        name = clean(body.get('name', ''), 80)
        email = clean(body.get('email', ''), 150).lower()
        password = body.get('password', '')
        require(name and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email), 400, 'Enter a name and valid email address.')
        require(isinstance(password, str) and 8 <= len(password) <= 128, 400, 'Password must have 8 to 128 characters.')
        uid = uuid.uuid4().hex
        return {'id': uid, 'name': name, 'email': email, 'role': role, 'passwordHash': password_hash(password),
                'department': clean(body.get('department', 'General Medicine'), 80) if role == 'doctor' else '',
                'createdAt': datetime.now(timezone.utc).isoformat()}

    def scoped_appointments(self, user):
        return sorted([a for a in self.store.list('APPT#') if self.can_view(user, a)], key=lambda a: a['when'], reverse=True)

    @staticmethod
    def can_view(user, appointment):
        return user['role'] == 'admin' or user['id'] in (appointment['patientId'], appointment['doctorId'])

    @staticmethod
    def when(value):
        require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', value), 400, 'Select a valid appointment time.')
        try:
            parsed = datetime.strptime(value, '%Y-%m-%dT%H:%M').replace(tzinfo=IST)
        except ValueError:
            raise ApiError(400, 'Invalid calendar date.')
        now = datetime.now(IST)
        require(now < parsed < now + timedelta(days=180), 400, 'Choose a future time within 180 days.')
        require(9 <= parsed.hour < 18 and parsed.minute in (0, 30), 400, 'Slots are every 30 minutes, 09:00 to 17:30 IST.')
        return value

    def handle(self, event):
        try:
            return self.route(event)
        except ApiError as exc:
            return self.response(exc.code, {'error': exc.message})
        except Conflict as exc:
            return self.response(409, {'error': str(exc)})
        except Exception:
            logging.exception('Request failed')
            return self.response(500, {'error': 'Server error. Please try again.'})

    def route(self, event):
        method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
        path = event.get('rawPath', '/').rstrip('/') or '/'
        if method == 'GET' and path in ('/', '/index.html', '/styles.css', '/app.js'):
            filename = {'/': 'index.html', '/index.html': 'index.html', '/styles.css': 'styles.css', '/app.js': 'app.js'}[path]
            mime = {'index.html': 'text/html; charset=utf-8', 'styles.css': 'text/css; charset=utf-8', 'app.js': 'text/javascript; charset=utf-8'}[filename]
            return self.response(200, (ROOT / 'frontend' / filename).read_text(encoding='utf-8'), content_type=mime)
        if path == '/api/health' and method == 'GET':
            return self.response(200, {'status': 'ok', 'application': 'CareFlow', 'storage': 'DynamoDB' if self.mode == 'aws' else 'SQLite', 'timezone': 'Asia/Kolkata'})
        body = {}
        if method in ('POST', 'PATCH', 'DELETE'):
            headers = {k.lower(): v for k, v in event.get('headers', {}).items()}
            require(headers.get('content-type', '').split(';')[0].lower() == 'application/json', 415, 'Send application/json.')
            require(headers.get('sec-fetch-site', '') != 'cross-site', 403, 'Cross-site requests are not allowed.')
            origin = headers.get('origin')
            if origin:
                require(urlsplit(origin).netloc == headers.get('host'), 403, 'Origin does not match this application.')
            raw = event.get('body') or '{}'
            if event.get('isBase64Encoded'):
                try:
                    raw = base64.b64decode(raw, validate=True).decode()
                except (ValueError, UnicodeError):
                    raise ApiError(400, 'Invalid request encoding.')
            require(len(raw.encode()) <= 32768, 413, 'Request is too large.')
            try:
                body = json.loads(raw)
            except ValueError:
                raise ApiError(400, 'Invalid JSON body.')
            require(isinstance(body, dict), 400, 'Expected a JSON object.')
        if path == '/api/setup' and method == 'GET':
            return self.response(200, {'needsAdmin': self.store.get('META#ADMIN') is None})
        if path in ('/api/setup', '/api/register') and method == 'POST':
            role = 'admin' if path == '/api/setup' else 'patient'
            if role == 'admin':
                require(self.store.get('META#ADMIN') is None, 409, 'Administrator already configured.')
                key = body.get('setupKey', '')
                require(isinstance(key, str) and hmac.compare_digest(key.encode(), self.setup_key.encode()), 403, 'Incorrect administrator setup key.')
            user = self.new_user(body, role)
            changes = [('USER#' + user['id'], user, None), ('EMAIL#' + user['email'], {'id': user['id']}, None)]
            if role == 'admin':
                changes.append(('META#ADMIN', {'id': user['id']}, None))
            self.store.write(changes)
            return self.create_session(user)
        if path == '/api/login' and method == 'POST':
            email = clean(body.get('email', ''), 150).lower()
            password = body.get('password', '')
            require(isinstance(password, str) and len(password) <= 128, 400, 'Invalid password.')
            # A shared per-email window prevents repeated guesses across Lambda instances.
            rate_key = 'RATE#' + hashlib.sha256(email.encode()).hexdigest()
            previous = self.store.get(rate_key)
            current = previous if previous and previous['until'] > time.time() else {'count': 0, 'until': int(time.time()) + 300}
            require(current['count'] < 10, 429, 'Too many attempts. Try again in five minutes.')
            self.store.write([(rate_key, {**current, 'count': current['count'] + 1}, previous)])
            entry = self.store.get('EMAIL#' + email)
            user = self.store.get('USER#' + entry['id']) if entry else None
            require(user and matches(password, user['passwordHash']), 401, 'Incorrect email or password.')
            return self.create_session(user)
        require(path.startswith('/api/'), 404, 'Page not found.')
        user, session_key, session = self.session(event)
        role = user['role']
        if path == '/api/me' and method == 'GET':
            return self.response(200, {'user': public(user), 'mode': self.mode})
        if path == '/api/logout' and method == 'POST':
            self.store.write([(session_key, None, session)])
            return self.response(200, {'ok': True}, self.session_cookie('', 0))
        if path == '/api/doctors' and method == 'GET':
            return self.response(200, [public(u) for u in self.store.list('USER#') if u['role'] == 'doctor'])
        if path == '/api/users' and method == 'GET':
            require(role == 'admin', 403, 'Administrator access required.')
            return self.response(200, [public(u) for u in self.store.list('USER#')])
        if path == '/api/doctors' and method == 'POST':
            require(role == 'admin', 403, 'Administrator access required.')
            doctor = self.new_user(body, 'doctor')
            self.store.write([('USER#' + doctor['id'], doctor, None), ('EMAIL#' + doctor['email'], {'id': doctor['id']}, None)])
            return self.response(201, public(doctor))
        appointments = self.scoped_appointments(user)
        if path == '/api/dashboard' and method == 'GET':
            users = self.store.list('USER#')
            return self.response(200, {'appointments': len(appointments), 'booked': sum(a['status'] == 'booked' for a in appointments),
                                      'completed': sum(a['status'] == 'completed' for a in appointments),
                                      'doctors': sum(u['role'] == 'doctor' for u in users),
                                      'patients': sum(u['role'] == 'patient' for u in users) if role == 'admin' else None,
                                      'recent': appointments[:5]})
        if path == '/api/appointments' and method == 'GET':
            return self.response(200, appointments)
        if path == '/api/appointments' and method == 'POST':
            require(role == 'patient', 403, 'Only patients can book appointments.')
            doctor_id = clean(body.get('doctorId', ''), 40)
            doctor = self.store.get('USER#' + doctor_id)
            require(doctor and doctor['role'] == 'doctor', 400, 'Choose a valid doctor.')
            when = self.when(body.get('when', ''))
            reason = clean(body.get('reason', ''), 500)
            require(reason, 400, 'Please enter the reason for your visit.')
            uid = uuid.uuid4().hex
            record = {'id': uid, 'patientId': user['id'], 'patientName': user['name'], 'doctorId': doctor_id,
                      'doctorName': doctor['name'], 'department': doctor['department'], 'when': when, 'reason': reason,
                      'status': 'booked', 'createdAt': datetime.now(timezone.utc).isoformat()}
            self.store.write([('APPT#' + uid, record, None), ('SLOT#' + doctor_id + '#' + when, {'appointmentId': uid}, None),
                              ('PATIENTSLOT#' + user['id'] + '#' + when, {'appointmentId': uid}, None)])
            return self.response(201, record)
        match = re.fullmatch(r'/api/appointments/([a-f0-9]{32})/(cancel|complete|reschedule)', path)
        if match and method == 'POST':
            uid, action = match.groups()
            old = self.store.get('APPT#' + uid)
            require(old, 404, 'Appointment not found.')
            require(self.can_view(user, old), 403, 'You cannot change this appointment.')
            require(old['status'] == 'booked', 409, 'Only booked appointments can be changed.')
            new = dict(old)
            if action == 'complete':
                require(role in ('doctor', 'admin'), 403, 'Only a doctor or administrator can complete a visit.')
                require(datetime.fromisoformat(old['when']).replace(tzinfo=IST) <= datetime.now(IST), 409, 'The appointment time has not arrived yet.')
                new['status'] = 'completed'
            elif action == 'cancel':
                new['status'] = 'cancelled'
            else:
                require(role in ('patient', 'admin'), 403, 'Only the patient or administrator can reschedule.')
                new['when'] = self.when(body.get('when', ''))
                require(new['when'] != old['when'], 400, 'Choose a different appointment time.')
            changes = [('APPT#' + uid, new, old)]
            if action != 'complete':
                changes += [('SLOT#' + old['doctorId'] + '#' + old['when'], None, {'appointmentId': uid}),
                            ('PATIENTSLOT#' + old['patientId'] + '#' + old['when'], None, {'appointmentId': uid})]
            if action == 'reschedule':
                changes += [('SLOT#' + old['doctorId'] + '#' + new['when'], {'appointmentId': uid}, None),
                            ('PATIENTSLOT#' + old['patientId'] + '#' + new['when'], {'appointmentId': uid}, None)]
            self.store.write(changes)
            return self.response(200, new)
        if path == '/api/records' and method == 'GET':
            allowed = {a['id'] for a in appointments}
            return self.response(200, [r for r in self.store.list('RECORD#') if r['appointmentId'] in allowed])
        if path == '/api/records' and method == 'POST':
            require(role in ('doctor', 'admin'), 403, 'Only clinical staff can write consultation records.')
            aid = clean(body.get('appointmentId', ''), 40)
            appt = self.store.get('APPT#' + aid)
            require(appt and self.can_view(user, appt), 403, 'Choose an appointment assigned to you.')
            require(appt['status'] != 'cancelled', 409, 'Cannot add a record to a cancelled appointment.')
            require(datetime.fromisoformat(appt['when']).replace(tzinfo=IST) <= datetime.now(IST), 409, 'The appointment time has not arrived yet.')
            diagnosis = clean(body.get('diagnosis', ''), 2000)
            require(diagnosis, 400, 'Enter a diagnosis or consultation summary.')
            record = {'id': uuid.uuid4().hex, 'appointmentId': aid, 'patientName': appt['patientName'],
                      'doctorName': appt['doctorName'], 'diagnosis': diagnosis, 'prescription': clean(body.get('prescription', ''), 2000),
                      'authorId': user['id'], 'createdAt': datetime.now(timezone.utc).isoformat()}
            self.store.write([('RECORD#' + record['id'], record, None), ('APPT#' + aid, appt, appt)])
            return self.response(201, record)
        if path == '/api/invoices' and method == 'GET':
            require(role != 'doctor', 403, 'Billing is available to patients and administrators.')
            return self.response(200, [r for r in self.store.list('INVOICE#') if role == 'admin' or r['patientId'] == user['id']])
        if path == '/api/invoices' and method == 'POST':
            require(role == 'admin', 403, 'Only administrators can issue invoices.')
            aid = clean(body.get('appointmentId', ''), 40)
            appt = self.store.get('APPT#' + aid)
            require(appt and appt['status'] != 'cancelled', 400, 'Select a valid appointment.')
            amount = body.get('amount', '')
            require(isinstance(amount, str) and re.fullmatch(r'\d{1,6}(\.\d{1,2})?', amount), 400, 'Enter a positive amount with at most two decimals.')
            whole, _, fraction = amount.partition('.')
            paise = int(whole) * 100 + int(fraction.ljust(2, '0') or '0')
            require(0 < paise <= 100000000, 400, 'Amount must be between INR 0.01 and 10,00,000.')
            record = {'id': aid, 'appointmentId': aid, 'patientId': appt['patientId'], 'patientName': appt['patientName'],
                      'amountPaise': paise, 'description': clean(body.get('description', 'Consultation'), 200),
                      'status': 'unpaid', 'createdAt': datetime.now(timezone.utc).isoformat()}
            self.store.write([('INVOICE#' + aid, record, None), ('APPT#' + aid, appt, appt)])
            return self.response(201, record)
        match = re.fullmatch(r'/api/invoices/([a-f0-9]{32})/paid', path)
        if match and method == 'POST':
            require(role == 'admin', 403, 'Only administrators can record payments.')
            key = 'INVOICE#' + match.group(1)
            old = self.store.get(key)
            require(old, 404, 'Invoice not found.')
            require(old['status'] == 'unpaid', 409, 'Invoice already marked paid.')
            new = {**old, 'status': 'paid', 'paidAt': datetime.now(timezone.utc).isoformat()}
            self.store.write([(key, new, old)])
            return self.response(200, new)
        raise ApiError(404, 'Endpoint not found.')
