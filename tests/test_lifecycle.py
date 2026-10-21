import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


class LifecycleTests(unittest.TestCase):
    def test_cancel_stops_only_registered_child_process(self):
        from tokenview.store import Store
        from tokenview.providers import Provider
        with tempfile.TemporaryDirectory() as d:
            provider=Provider(Store(Path(d)))
            process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],creationflags=0x08000000)
            try:
                provider.register('test',process)
                provider.cancel('test')
                self.assertIsNotNone(process.poll())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def test_codex_delete_revokes_then_removes_owned_profile(self):
        from tokenview.store import Store
        from tokenview.service import Controller
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d))
            a=store.add_account('codex','A')
            profile=store.profile(a)
            (profile/'cache.txt').write_text('fixture','utf-8')
            controller=Controller(store)
            controller.provider.revoke=lambda account: None  # Only replace external CLI logout.
            controller.remove(a)
            deadline=time.monotonic()+2
            while a.id in store.accounts and time.monotonic()<deadline:
                controller.collect()
                time.sleep(.01)
            controller.close()
            self.assertNotIn(a.id,store.accounts)
            self.assertFalse(profile.exists())


if __name__=='__main__':
    unittest.main()
