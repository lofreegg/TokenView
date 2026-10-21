import json
from pathlib import Path
import tempfile
import threading
import time
import unittest


class AgyAccountTests(unittest.TestCase):
    def test_shutdown_and_authorization_commit_share_one_cancellation_boundary(self):
        from tokenview.store import Store
        from tokenview.service import Controller
        with tempfile.TemporaryDirectory() as root:
            controller = Controller(Store(root))
            cancel = threading.Event()
            controller.running['pending'] = ('login', cancel)
            started, finished = threading.Event(), threading.Event()
            def close():
                started.set()
                controller.close()
                finished.set()
            # Model an in-progress credential commit using its actual lock.
            controller.provider.lock.acquire()
            thread = threading.Thread(target=close)
            thread.start()
            try:
                self.assertTrue(started.wait(1))
                self.assertFalse(finished.wait(.1))
                self.assertFalse(cancel.is_set(), 'shutdown cancellation raced an active credential commit')
            finally:
                controller.provider.lock.release()
                thread.join(2)
            self.assertTrue(finished.is_set())
            self.assertTrue(cancel.is_set())

    def test_removed_account_discards_a_previously_queued_login_url(self):
        from tokenview.store import Store
        from tokenview.service import Controller
        with tempfile.TemporaryDirectory() as root:
            store = Store(root)
            account = store.add_account('antigravity', 'A')
            controller = Controller(store)
            # Replace only the external OAuth flow, preserve real event dispatch.
            controller.provider.authorize = lambda a, open_url, cancel: open_url('https://accounts.google.com/test')
            try:
                controller.authorize(account, None)
                deadline = time.monotonic() + 2
                while controller.events.empty() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertFalse(controller.events.empty())
                controller.remove(account)
                _, notices = controller.collect()
                self.assertFalse(any(kind == 'open_url' for kind, _ in notices))
            finally:
                controller.close()

    def test_cancelled_query_does_not_require_credentials_or_start_an_engine(self):
        from tokenview.store import Store
        from tokenview.providers import Provider, ProviderError
        with tempfile.TemporaryDirectory() as root:
            store = Store(root)
            account = store.add_account('antigravity', 'A')
            provider = Provider(store)
            cancel = threading.Event()
            cancel.set()
            with self.assertRaisesRegex(ProviderError, '取消'):
                provider.fetch(account, cancel)
            self.assertFalse(provider.active)
            self.assertFalse(list(Path(root).glob('tokenview-agy-*')))

    def test_credentials_are_encrypted_isolated_and_deleted_per_account(self):
        from tokenview.store import Store
        with tempfile.TemporaryDirectory() as root:
            store = Store(root)
            a = store.add_account('antigravity', 'A')
            b = store.add_account('antigravity', 'B')
            for account, token in [(a, 'private-refresh-A'), (b, 'private-refresh-B')]:
                self.assertTrue(store.save_credentials(account.id, account.generation,
                    {'email': account.name, 'refresh_token': token}))
            restored = Store(root)
            self.assertEqual(restored.credentials(a.id)['refresh_token'], 'private-refresh-A')
            self.assertEqual(restored.credentials(b.id)['refresh_token'], 'private-refresh-B')
            self.assertNotIn('private-refresh-', (Path(root) / 'state.json').read_text())
            store.remove_account(a.id)
            self.assertFalse(store.save_credentials(a.id, a.generation, {'refresh_token': 'late'}))
            self.assertNotIn(a.id, store.encrypted)
            self.assertEqual(store.credentials(b.id)['refresh_token'], 'private-refresh-B')

    def test_quota_windows_come_from_explicit_bucket_fields(self):
        from tokenview.agy_accounts import parse_summary
        response = {'groups': [{'displayName': 'Gemini Models', 'buckets': [
            {'displayName': 'Five Hour Limit Remaining', 'window': '5h',
             'remainingFraction': .42, 'resetTime': '2026-10-12T08:00:00Z'},
            {'displayName': 'Weekly Limit Remaining', 'window': '7d',
             'remainingFraction': .68, 'resetTime': '2026-10-18T08:00:00Z'}]}]}
        metrics = parse_summary(response)['metrics']
        self.assertEqual([(m['period'], m['value'], m['group']) for m in metrics],
                         [('5h', 42, 'Gemini'), ('weekly', 68, 'Gemini')])
        response['groups'][0]['buckets'][0]['remainingFraction'] = 0
        self.assertEqual(parse_summary(response)['metrics'][0]['value'], 0)

    def test_unknown_model_fraction_is_not_invented_as_a_weekly_window(self):
        from tokenview.agy_accounts import parse_summary
        from tokenview.providers import ProviderError
        with self.assertRaises(ProviderError):
            parse_summary({'groups': [{'displayName': 'Gemini Models', 'buckets': [
                {'displayName': 'Model quota', 'remainingFraction': .8,
                 'resetTime': '2026-10-18T08:00:00Z'}]}]})

    def test_oauth_url_cannot_open_an_untrusted_site_or_foreign_callback(self):
        from tokenview.agy_accounts import login_url
        from tokenview.providers import ProviderError
        good = 'https://accounts.google.com/o/oauth2/auth?state=test&redirect_uri=http%3A%2F%2Flocalhost%3A51234%2Foauth-callback'
        self.assertIn('select_account', login_url(good, 51234))
        with self.assertRaises(ProviderError):
            login_url(good.replace('accounts.google.com', 'evil.example'), 51234)
        with self.assertRaises(ProviderError):
            login_url(good, 51235)


if __name__ == '__main__':
    unittest.main()
