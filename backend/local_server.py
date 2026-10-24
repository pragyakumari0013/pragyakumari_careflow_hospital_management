import argparse
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from app import Application
from storage import SQLiteStore

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description='Run CareFlow with Python. No pip or npm required.')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()
    data = ROOT / 'data'
    data.mkdir(exist_ok=True)
    key_file = data / 'setup-key.txt'
    if not key_file.exists():
        key_file.write_text(secrets.token_urlsafe(32), encoding='utf-8')
        try:
            key_file.chmod(0o600)
        except OSError:
            pass
    app = Application(SQLiteStore(data / 'careflow.db'), os.environ.get('ADMIN_SETUP_KEY') or key_file.read_text().strip())

    class Handler(BaseHTTPRequestHandler):
        def serve(self):
            try:
                length = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                self.send_error(400)
                return
            if not 0 <= length <= 32768:
                self.send_error(413)
                return
            try:
                body = self.rfile.read(length).decode('utf-8')
            except UnicodeError:
                self.send_error(400)
                return
            event = {'rawPath': self.path.split('?')[0], 'headers': dict(self.headers), 'body': body,
                     'requestContext': {'http': {'method': self.command}}}
            result = app.handle(event)
            payload = result['body'].encode('utf-8')
            self.send_response(result['statusCode'])
            for k, v in result['headers'].items():
                self.send_header(k, v)
            for cookie in result.get('cookies', []):
                self.send_header('Set-Cookie', cookie)
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        do_GET = do_POST = do_PATCH = do_DELETE = do_OPTIONS = serve

        def log_message(self, fmt, *args):
            print(f'{self.address_string()} {fmt % args}')

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f'CareFlow is running at http://{args.host}:{args.port}', flush=True)
    if app.store.get('META#ADMIN') is None:
        print('Administrator setup key: ' + app.setup_key, flush=True)
    print('Press Ctrl+C to stop. Data remains in the data folder.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nServer stopped.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
