import json
from pathlib import Path
import tempfile
import unittest


class PersonalChangesTests(unittest.TestCase):
    def test_no_feed_space_reserved(self):
        from tokenview.layout import panel_height
        self.assertEqual(panel_height(2, True, 900), panel_height(2, False, 900))

    def test_drag_moves_offset_and_suppresses_click(self):
        from tokenview.interaction import DockInteraction
        state = DockInteraction()
        state.press(100, 100)
        state.move(124, 112, 1.2)
        self.assertEqual(state.offset, (20, 10))
        self.assertTrue(state.release())
        state.press(100, 100)
        self.assertFalse(state.release())

    def test_hover_expands_after_delay_but_not_during_drag(self):
        from tokenview.interaction import DockInteraction
        state = DockInteraction()
        self.assertFalse(state.hover(True, 1.0))
        self.assertTrue(state.hover(True, 1.3))
        state.press(10, 10)
        self.assertFalse(state.hover(True, 2.0))
        state.release()
        state.hover(False, 3.0)
        self.assertFalse(state.hover(True, 3.1))

    def test_import_existing_accounts_without_copying_keys(self):
        from tokenview.store import Store
        from tokenview.integrated import connect_existing
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / 'myagents'
            (home / 'codex').mkdir(parents=True)
            (home / 'codex' / 'auth.json').write_text('{}')
            (home / 'config.json').write_text(json.dumps({
                'managedCodexAuth': {'accountEmail': 'test@example.test'},
                'providerApiKeys': {'deepseek': 'TEST-SECRET-DO-NOT-COPY'}}))
            store = Store(root / 'data')
            connect_existing(store, home)
            self.assertEqual({a.product for a in store.accounts.values()}, {'codex', 'deepseek'})
            self.assertTrue(all(a.connection == 'myagents' for a in store.accounts.values()))
            self.assertNotIn('TEST-SECRET-DO-NOT-COPY', (store.root / 'state.json').read_text('utf-8'))
            connect_existing(store, home)
            self.assertEqual(len(store.accounts), 2)

    def test_shared_codex_remove_never_logs_out_host(self):
        from tokenview.store import Store
        from tokenview.service import Controller
        with tempfile.TemporaryDirectory() as temp:
            store = Store(temp)
            account = store.add_account('codex', 'MyAgents')
            account.connection = 'myagents'
            controller = Controller(store)
            try:
                controller.remove(account)
                self.assertNotIn(account.id, store.accounts)
            finally:
                controller.close()
