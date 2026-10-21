import tempfile
import unittest
from pathlib import Path


class ServiceTests(unittest.TestCase):
    def test_failure_keeps_last_success_and_marks_error(self):
        from tokenview.store import Store
        with tempfile.TemporaryDirectory() as d:
            store = Store(Path(d))
            a = store.add_account('codex', 'A')
            store.update_snapshot(a.id, a.generation, {'at': 100, 'metrics': []})
            store.update_snapshot(a.id, a.generation, None, '网络不可用')
            self.assertEqual(a.snapshot['at'], 100)
            self.assertEqual(a.error, '网络不可用')

    def test_feed_selects_first_item_inside_feed_list(self):
        from tokenview.feed import parse_feed
        html = '''<p>wrong</p><ul id="feed-list"><li class="feed-item"><span class="chip">NOTE</span>
        <a class="feed-time" href="https://x.com/thsottiaux/status/123">2m ago</a>
        <p class="feed-text">First &amp; latest <a href="https://t.co/abc">link</a></p></li>
        <li><p class="feed-text">Old item</p></li></ul>'''
        post = parse_feed(html)
        self.assertEqual(post['text'], 'First & latest link')
        self.assertEqual(post['url'], 'https://x.com/thsottiaux/status/123')
        self.assertEqual(post['kind'], 'NOTE')

    def test_missing_feed_does_not_fallback_to_arbitrary_text(self):
        from tokenview.feed import parse_feed
        with self.assertRaises(ValueError):
            parse_feed('<html>some page text</html>')

    def test_alert_deduplicates_until_reset_or_recovery(self):
        from tokenview.service import AlertTracker
        tracker = AlertTracker()
        metrics = [{'label': '5H', 'period': '5h', 'unit': 'percent', 'value': 10, 'reset': 1000}]
        self.assertTrue(tracker.check('A', metrics, 15))
        self.assertFalse(tracker.check('A', metrics, 15))
        metrics[0]['reset'] = 2000
        self.assertTrue(tracker.check('A', metrics, 15))
        metrics[0]['value'] = 50
        self.assertFalse(tracker.check('A', metrics, 15))

    def test_balance_alert_uses_currency_amount_not_percentage(self):
        from tokenview.service import AlertTracker
        tracker=AlertTracker()
        metrics=[{'label':'余额','unit':'CNY','value':4.0}]
        self.assertTrue(tracker.check('D',metrics,15,money_threshold=5))
        self.assertFalse(tracker.check('D',metrics,15,money_threshold=5))


if __name__ == '__main__':
    unittest.main()
