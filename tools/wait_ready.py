"""Wait for local app readiness when systemd starts LabUI."""
import argparse
import time
import urllib.error
import urllib.request

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url', default='http://127.0.0.1:8770/api/ready')
parser.add_argument('--timeout', type=float, default=180)
args = parser.parse_args()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
deadline = time.monotonic() + args.timeout
while time.monotonic() < deadline:
    try:
        with opener.open(args.url, timeout=3) as response:
            if response.status == 200:
                print('LabUI is ready:', args.url)
                break
    except (urllib.error.URLError, TimeoutError):
        pass
    time.sleep(1)
else:
    raise SystemExit('LabUI did not become ready; inspect journalctl --user -u labui')
