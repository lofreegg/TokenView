import unittest
from pathlib import Path


class ProviderTests(unittest.TestCase):
    def test_codex_windows_are_mapped_by_duration_not_position(self):
        from tokenview.providers import parse_codex
        data = {'rateLimits': {'primary': {'windowDurationMins': 10080, 'usedPercent': 59, 'resetsAt': 2000000000},
                               'secondary': {'windowDurationMins': 300, 'usedPercent': 38, 'resetsAt': 1900000000}}}
        result = parse_codex(data)
        self.assertEqual([(m['label'], m['value']) for m in result['metrics']], [('5H', 62), ('周', 41)])

    def test_codex_missing_week_is_not_estimated(self):
        from tokenview.providers import parse_codex
        data = {'rateLimitsByLimitId': {'codex': {'primary': {'windowDurationMins': 300, 'usedPercent': 20}}}}
        self.assertEqual(len(parse_codex(data)['metrics']), 1)

    def test_invalid_percentage_fails_closed(self):
        from tokenview.providers import parse_codex, ProviderError
        for value in (-1, 101, float('nan'), None, True):
            with self.subTest(value=value), self.assertRaises(ProviderError):
                parse_codex({'rateLimits': {'primary': {'windowDurationMins': 300, 'usedPercent': value}}})

    def test_agy_preserves_both_model_groups(self):
        from tokenview.providers import parse_agy
        response = '\n'.join(f'{group}\t{period}\t{value}%\t2030-01-01T10:00:00Z' for group, period, value in [
            ('Gemini Models', 'Five Hour Limit Remaining', 62), ('Gemini Models', 'Weekly Limit Remaining', 41),
            ('Claude and GPT models', 'Five Hour Limit Remaining', 80), ('Claude and GPT models', 'Weekly Limit Remaining', 30)])
        snapshot = parse_agy({'status': 'SUCCESS', 'response': response})
        self.assertEqual([m['value'] for m in snapshot['metrics']], [62, 41, 80, 30])
        self.assertEqual(snapshot['metrics'][0]['group'], 'Gemini')

    def test_deepseek_amounts_and_currency_are_not_percentages(self):
        from tokenview.providers import parse_deepseek
        value = {'is_available': True, 'balance_infos': [{'currency': 'CNY', 'total_balance': '12.30', 'granted_balance': '2.30', 'topped_up_balance': '10.00'}]}
        snapshot = parse_deepseek(value)
        self.assertEqual([(m['value'], m['unit']) for m in snapshot['metrics']], [(12.3, 'CNY'), (2.3, 'CNY')])

    def test_deepseek_missing_currency_not_invented(self):
        from tokenview.providers import parse_deepseek, ProviderError
        with self.assertRaises(ProviderError):
            parse_deepseek({'is_available': True, 'balance_infos': [{'total_balance': '1', 'granted_balance': '0'}]})

    def test_profile_env_does_not_mutate_process_home(self):
        import os
        from tokenview.providers import profile_env
        before = dict(os.environ)
        env_a = profile_env('antigravity', Path('D:/first'))
        env_b = profile_env('antigravity', Path('D:/second'))
        self.assertNotEqual(env_a['USERPROFILE'], env_b['USERPROFILE'])
        self.assertEqual(dict(os.environ), before)
        self.assertNotEqual(env_a['APPDATA'], env_b['APPDATA'])


if __name__ == '__main__':
    unittest.main()
