import tempfile
import unittest
from pathlib import Path


class CoreTests(unittest.TestCase):
    def test_cache_and_selection_survive_restart(self):
        from tokenview.store import Store
        with tempfile.TemporaryDirectory() as d:
            store = Store(Path(d))
            acc = store.add_account('deepseek', '主账号', key='test-private-key')
            store.select('deepseek', acc.id)
            store.update_snapshot(acc.id, acc.generation, {'metrics': [{'label': '余额', 'value': 12.3}], 'at': 100})
            restored = Store(Path(d))
            self.assertEqual(restored.selected_product, 'deepseek')
            self.assertEqual(restored.selected_account, acc.id)
            self.assertEqual(restored.accounts[acc.id].snapshot['metrics'][0]['value'], 12.3)
            self.assertEqual(restored.secret(acc.id), 'test-private-key')
            self.assertNotIn('test-private-key', (Path(d) / 'state.json').read_text('utf-8'))

    def test_removed_account_rejects_late_result(self):
        from tokenview.store import Store
        with tempfile.TemporaryDirectory() as d:
            store = Store(Path(d))
            acc = store.add_account('codex', 'A')
            store.remove_account(acc.id)
            self.assertFalse(store.update_snapshot(acc.id, acc.generation, {'at': 123}))
            self.assertNotIn(acc.id, Store(Path(d)).accounts)

    def test_selecting_account_keeps_product(self):
        from tokenview.store import Store
        with tempfile.TemporaryDirectory() as d:
            store = Store(Path(d))
            first = store.add_account('antigravity', 'A')
            second = store.add_account('antigravity', 'B')
            store.select('antigravity', first.id)
            store.select('antigravity', second.id)
            self.assertEqual(store.selected_product, 'antigravity')
            self.assertEqual(store.selected_account, second.id)

    def test_invalid_refresh_and_capsule_size_rejected(self):
        from tokenview.store import Store
        with tempfile.TemporaryDirectory() as d:
            store = Store(Path(d))
            self.assertEqual(store.settings['refresh_seconds'], 600)
            with self.assertRaises(ValueError):
                store.set_settings(refresh_seconds=0)
            with self.assertRaises(ValueError):
                store.set_settings(capsule_scale=9)


if __name__ == '__main__':
    unittest.main()
