"""Read-only quota validation using the user's already-authorized current account.

Host files are never changed. Tokens are not printed or persisted to Store;
the isolated owner-only engine directory is removed at exit.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import tempfile
from tokenview.store import Store
from tokenview.providers import Provider
from tokenview.agy_accounts import Session, parse_summary
from tokenview.integrated import myagents_home


def main():
    base = myagents_home() / 'providers' / 'cliproxy' / 'antigravity-sub'
    active = json.loads((base / 'account-state.json').read_text('utf-8-sig'))['active']['id']
    auth_root = (base / 'accounts' / active / 'auth').resolve()
    if auth_root.parent.parent != (base / 'accounts').resolve():
        raise RuntimeError('invalid host account path')
    files = list(auth_root.glob('antigravity-*.json'))
    if len(files) != 1:
        raise RuntimeError('current account not unique')
    original = files[0].read_bytes()
    credential = json.loads(original)
    with tempfile.TemporaryDirectory(prefix='quota-probe-', dir=Path(__file__).resolve().parents[1] / 'test-artifacts') as root:
        store = Store(root)
        account = store.add_account('antigravity', 'quota probe')
        account.connection = 'myagents'
        provider = Provider(store)
        with Session(provider, account) as session:
            (session.auth / 'antigravity-account.json').write_text(json.dumps(credential), 'utf-8')
            session.start()
            files_loaded = session.wait_ready().get('files', [])
            own = [f for f in files_loaded if f.get('email') == credential['email']]
            assert len(own) == 1
            result = session.request('api-call', {'auth_index': own[0]['auth_index'], 'method': 'POST',
                'url': 'https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary',
                'header': {'Authorization': 'Bearer $TOKEN$', 'Content-Type': 'application/json',
                           'User-Agent': 'antigravity/2.22.0 windows/amd64'},
                'data': json.dumps({'project': credential['project_id']})})
            print('official_status', result.get('status_code'))
            if result.get('status_code') == 200:
                body = json.loads(result['body'])
                print('quota_only', json.dumps({key: body.get(key) for key in ('groups', 'buckets')}, ensure_ascii=False)[:7000])
                print('parsed', json.dumps(parse_summary(body), ensure_ascii=False))
        assert files[0].read_bytes() == original, 'host credentials changed'
        assert not store.encrypted, 'host credentials persisted'
        provider.close()


if __name__ == '__main__':
    main()
