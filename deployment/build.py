import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build():
    output = ROOT / 'deployment' / 'careflow-lambda.zip'
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for folder, pattern in (('backend', '*.py'), ('frontend', '*')):
            for source in sorted((ROOT / folder).glob(pattern)):
                if source.is_file() and source.name != 'local_server.py':
                    info = zipfile.ZipInfo(source.relative_to(ROOT).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    bundle.writestr(info, source.read_bytes())
        bundle.writestr('lambda_function.py', "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parent / 'backend'))\nfrom backend.lambda_function import lambda_handler\n")
    print('Built: ' + str(output))
    return output


if __name__ == '__main__':
    build()
