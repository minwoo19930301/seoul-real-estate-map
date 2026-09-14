"""Acquire the audited public source, reusing the existing local download when possible."""
from pathlib import Path
import hashlib
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / 'data' / 'seoul-contours.zip'
PREVIOUS = ROOT.parent / 'seoul-contours-feasibility' / 'seoul-contours.zip'
EXPECTED_SHA256 = '4fbe3c7e061b5974e7403ec116855304ed8ae321eebcc0d12c31ca8fb7be30bf'

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def main():
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    if DESTINATION.exists():
        if digest(DESTINATION) != EXPECTED_SHA256:
            raise SystemExit('기존 ZIP이 검증한 버전과 다릅니다. 원본을 덮어쓰지 않았습니다.')
        print(f'기존 검증 원본 사용: {DESTINATION}')
        return
    temporary = DESTINATION.with_suffix('.download')
    try:
        if PREVIOUS.exists() and digest(PREVIOUS) == EXPECTED_SHA256:
            shutil.copyfile(PREVIOUS, temporary)
        else:
            request = urllib.request.Request(
                'https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false',
                data=b'infId=OA-22241&seq=2&infSeq=1',
                headers={'User-Agent': 'SeoulElevationLocal/0.1 (public data download)'},
            )
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open('wb') as target:
                shutil.copyfileobj(response, target)
        if not zipfile.is_zipfile(temporary) or digest(temporary) != EXPECTED_SHA256:
            raise SystemExit('공급 파일이 변경됐거나 ZIP이 아닙니다. 자료 시점·구조·이용 조건을 재확인해 주세요.')
        temporary.replace(DESTINATION)
        print(f'검증 원본 준비: {DESTINATION} ({DESTINATION.stat().st_size:,} bytes)')
    finally:
        temporary.unlink(missing_ok=True)

if __name__ == '__main__':
    main()
