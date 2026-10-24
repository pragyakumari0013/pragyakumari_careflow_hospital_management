import base64
import concurrent.futures
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))
from app import Application, IST
from storage import SQLiteStore, Conflict, DynamoStore


class SystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SQLiteStore(Path(self.temp.name) / 'test.db')
        self.app = Application(self.store, 'test-key-that-is-long-enough-for-setup')
        self.cookies = {}
        self.make_user('admin', '/setup', setupKey=self.app.setup_key)
        self.doctor = self.call('/doctors', 'POST', {'name':'Dr. Sana Rao','email':'doctor@example.test','password':'DoctorTest123','department':'Cardiology'}, 'admin')[1]
        self.login('doctor', 'doctor@example.test', 'DoctorTest123')
        self.make_user('patient')
        self.make_user('other')
        self.when = (datetime.now(IST) + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0).strftime('%Y-%m-%dT%H:%M')

    def tearDown(self):
        self.temp.cleanup()

    def call(self, path, method='GET', body=None, who=None, headers=None):
        event = {'rawPath':'/api'+path,'requestContext':{'http':{'method':method}},'headers':{'content-type':'application/json',**(headers or {})},'body':json.dumps(body or {})}
        if who and who in self.cookies:
            event['cookies'] = [self.cookies[who]]
        result = self.app.handle(event)
        if result.get('cookies') and who:
            self.cookies[who] = result['cookies'][0].split(';')[0]
        return result['statusCode'], json.loads(result['body'])

    def make_user(self, who, path='/register', **extra):
        status, value = self.call(path, 'POST', {'name':who.title(),'email':who+'@example.test','password':'TestPassword123',**extra},who)
        self.assertEqual(status,200,value)
        return value['user']

    def login(self, who, email, password):
        status, value = self.call('/login','POST',{'email':email,'password':password},who)
        self.assertEqual(status,200,value)

    def book(self, who='patient', when=None, doctor=None):
        return self.call('/appointments','POST',{'doctorId':doctor or self.doctor['id'],'when':when or self.when,'reason':'Routine check'},who)

    def past_appointment(self):
        status, appt = self.book()
        self.assertEqual(status,201)
        past = {**appt,'when':(datetime.now(IST)-timedelta(days=1)).replace(hour=10,minute=0).strftime('%Y-%m-%dT%H:%M')}
        self.store.write([('APPT#'+appt['id'],past,appt)])
        return past

    def test_admin_setup_is_protected_and_single_use(self):
        self.assertEqual(self.call('/setup')[1]['needsAdmin'],False)
        self.assertEqual(self.call('/setup','POST',{'setupKey':self.app.setup_key})[0],409)
        fresh = Application(SQLiteStore(Path(self.temp.name)/'fresh.db'),self.app.setup_key)
        event={'rawPath':'/api/setup','requestContext':{'http':{'method':'POST'}},'headers':{'content-type':'application/json'},'body':json.dumps({'setupKey':'wrong'})}
        self.assertEqual(fresh.handle(event)['statusCode'],403)

    def test_patient_cannot_choose_admin_role(self):
        user = self.make_user('pretender',role='admin')
        self.assertEqual(user['role'],'patient')
        self.assertEqual(self.call('/users',who='pretender')[0],403)

    def test_duplicate_email_and_password_privacy(self):
        self.assertEqual(self.call('/register','POST',{'name':'Copy','email':'PATIENT@example.test','password':'OtherPassword123'})[0],409)
        for user in self.call('/users',who='admin')[1]:
            self.assertNotIn('passwordHash',user)
        self.assertEqual(self.call('/login','POST',{'email':'patient@example.test','password':'wrong'})[0],401)

    def test_login_rate_limit(self):
        for _ in range(10):
            self.assertEqual(self.call('/login','POST',{'email':'absent@example.test','password':'wrong'})[0],401)
        self.assertEqual(self.call('/login','POST',{'email':'absent@example.test','password':'wrong'})[0],429)

    def test_logout_revokes_session(self):
        old = self.cookies['patient']
        self.assertEqual(self.call('/logout','POST',{},'patient')[0],200)
        self.cookies['patient']=old
        self.assertEqual(self.call('/me',who='patient')[0],401)

    def test_booking_conflict_and_isolation(self):
        status, appointment = self.book()
        self.assertEqual(status,201)
        self.assertEqual(self.book('other')[0],409)
        self.assertEqual(self.call('/appointments',who='other')[1],[])
        self.assertEqual(len(self.call('/appointments',who='doctor')[1]),1)
        self.assertEqual(self.call('/appointments/'+appointment['id']+'/cancel','POST',{},'other')[0],403)
        self.assertEqual(self.call('/appointments/'+appointment['id']+'/complete','POST',{},'patient')[0],403)

    def test_patient_cannot_double_book_different_doctors(self):
        self.book()
        status, doctor = self.call('/doctors','POST',{'name':'Dr. Two','email':'two@example.test','password':'DoctorTest123'},'admin')
        self.assertEqual(status,201)
        self.assertEqual(self.book(doctor=doctor['id'])[0],409)

    def test_concurrent_booking_has_one_winner(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda who:self.book(who)[0], ['patient','other']))
        self.assertEqual(sorted(results),[201,409])

    def test_cancel_releases_slot_and_is_idempotent_conflict(self):
        _, appointment = self.book()
        path='/appointments/'+appointment['id']+'/cancel'
        self.assertEqual(self.call(path,'POST',{},'patient')[0],200)
        self.assertEqual(self.call(path,'POST',{},'patient')[0],409)
        self.assertEqual(self.book('other')[0],201)

    def test_reschedule_is_atomic(self):
        _, a=self.book()
        later=self.when.replace('10:00','11:00')
        self.assertEqual(self.book('other',later)[0],201)
        path='/appointments/'+a['id']+'/reschedule'
        self.assertEqual(self.call(path,'POST',{'when':later},'patient')[0],409)
        self.assertEqual(self.store.get('APPT#'+a['id'])['when'],self.when)
        self.assertIsNotNone(self.store.get('SLOT#'+self.doctor['id']+'#'+self.when))
        free=self.when.replace('10:00','12:00')
        self.assertEqual(self.call(path,'POST',{'when':free},'patient')[0],200)
        self.assertEqual(self.book('other')[0],201)

    def test_invalid_dates_slots_and_future_records(self):
        for when in ('2026-02-30T10:00','2000-01-01T10:00',self.when.replace('10:00','22:00'),self.when.replace('10:00','10:15')):
            self.assertEqual(self.book(when=when)[0],400)
        _,a=self.book()
        self.assertEqual(self.call('/appointments/'+a['id']+'/complete','POST',{},'doctor')[0],409)
        self.assertEqual(self.call('/records','POST',{'appointmentId':a['id'],'diagnosis':'Future record'},'doctor')[0],409)

    def test_consultation_records_and_completion(self):
        a=self.past_appointment()
        body={'appointmentId':a['id'],'diagnosis':'Routine examination','prescription':'Follow up in one month'}
        self.assertEqual(self.call('/records','POST',body,'patient')[0],403)
        self.assertEqual(self.call('/records','POST',body,'doctor')[0],201)
        self.assertEqual(len(self.call('/records',who='patient')[1]),1)
        self.assertEqual(self.call('/records',who='other')[1],[])
        self.assertEqual(self.call('/appointments/'+a['id']+'/complete','POST',{},'doctor')[0],200)

    def test_invoice_exact_amount_and_permissions(self):
        _,a=self.book()
        body={'appointmentId':a['id'],'amount':'450.99','description':'Consultation'}
        self.assertEqual(self.call('/invoices','POST',body,'patient')[0],403)
        status, invoice=self.call('/invoices','POST',body,'admin')
        self.assertEqual(status,201)
        self.assertEqual(invoice['amountPaise'],45099)
        self.assertEqual(self.call('/invoices','POST',body,'admin')[0],409)
        self.assertEqual(self.call('/invoices',who='other')[1],[])
        self.assertEqual(self.call('/invoices/'+a['id']+'/paid','POST',{},'patient')[0],403)
        self.assertEqual(self.call('/invoices/'+a['id']+'/paid','POST',{},'admin')[0],200)
        self.assertEqual(self.call('/invoices/'+a['id']+'/paid','POST',{},'admin')[0],409)

    def test_invalid_json_csrf_and_auth(self):
        self.assertEqual(self.call('/users')[0],401)
        self.assertEqual(self.call('/login','POST',{},headers={'sec-fetch-site':'cross-site'})[0],403)
        self.assertEqual(self.call('/login','POST',{},headers={'origin':'https://evil.test','host':'localhost'})[0],403)
        event={'rawPath':'/api/register','requestContext':{'http':{'method':'POST'}},'headers':{'content-type':'application/json'},'body':'['}
        self.assertEqual(self.app.handle(event)['statusCode'],400)
        event['body']='[]'
        self.assertEqual(self.app.handle(event)['statusCode'],400)
        event['body']=base64.b64encode(b'{}').decode();event['isBase64Encoded']=True
        self.assertEqual(self.app.handle(event)['statusCode'],400)

    def test_static_assets_and_cookie_flags(self):
        for path in ('/','/app.js','/styles.css'):
            response=self.app.handle({'rawPath':path,'requestContext':{'http':{'method':'GET'}}})
            self.assertEqual(response['statusCode'],200)
            self.assertIn('content-security-policy',response['headers'])
        self.assertIn('HttpOnly',self.app.session_cookie('x'))
        self.assertIn('Secure',Application(self.store,'key','aws').session_cookie('x'))
        self.assertEqual(self.call('/health')[1]['storage'],'SQLite')

    def test_store_rollback_and_dynamo_transaction_shape(self):
        self.store.write([('X',{'v':1},None)])
        with self.assertRaises(Conflict):
            self.store.write([('Y',{'v':2},None),('X',{'v':3},None)])
        self.assertIsNone(self.store.get('Y'))
        class Fake:
            def transact_write_items(self, **args):
                self.request=args
        # This adapter check requires boto3 only in the development environment.
        try:
            import botocore.exceptions
        except ImportError:
            return
        dynamo=DynamoStore.__new__(DynamoStore);dynamo.table='test';dynamo.db=Fake()
        dynamo.write([('SESSION#x',{'expires':123,'userId':'a'},None)])
        put=dynamo.db.request['TransactItems'][0]['Put']
        self.assertEqual(put['Item']['expires'],{'N':'123'})
        self.assertEqual(put['ConditionExpression'],'attribute_not_exists(pk)')


if __name__ == '__main__':
    unittest.main(verbosity=2)
