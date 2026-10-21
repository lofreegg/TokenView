"""Check the installed OAuth engine without opening a browser or using tokens."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import tempfile
import threading
import time
import urllib.parse
from tokenview.store import Store
from tokenview.providers import Provider
from tokenview.agy_accounts import Session, authorize


def main():
    with tempfile.TemporaryDirectory(prefix='agy-isolation-', dir=Path(__file__).resolve().parents[1] / 'test-artifacts') as root:
        store = Store(root)
        account = store.add_account('antigravity', 'probe')
        provider = Provider(store)
        with Session(provider, account) as session:
            session.start()
            files = session.wait_ready().get('files')
            assert files == [], 'isolated engine imported credentials from outside its own directory'
            port = session.port
        assert not list(Path(root).glob('tokenview-agy-*')), 'temporary files remain'
        cancel = threading.Event()
        result = {}
        def observe(url):
            parsed = urllib.parse.urlsplit(url)
            args = urllib.parse.parse_qs(parsed.query)
            callback = urllib.parse.urlsplit(args['redirect_uri'][0])
            result.update(oauth_host=parsed.hostname, callback_host=callback.hostname,
                          callback_port=callback.port, account_picker='select_account' in args.get('prompt', [''])[0])
            cancel.set()
        try:
            authorize(provider, account, observe, cancel)
        except Exception as exc:
            assert cancel.is_set(), str(exc)
        assert result.get('oauth_host') == 'accounts.google.com', result
        assert result.get('callback_host') == 'localhost', result
        assert result.get('account_picker'), result
        assert not store.encrypted, 'cancelled authorization saved credentials'
        assert not list(Path(root).glob('tokenview-agy-*')), 'cancelled login left credential files'
        provider.close()
        print(json.dumps(dict(result, isolated_service=True, cleanup=True, credentials_used=False)))


if __name__ == '__main__':
    main()
