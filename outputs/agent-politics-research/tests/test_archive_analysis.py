import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from analyze_archived_agentdojo import classify, summarize


class ArchiveSemantics(unittest.TestCase):
    def test_clean_security_sentinel_is_not_attack_success(self):
        s = summarize([{'utility':True,'security':True}], 'clean')
        self.assertIsNone(s['attack_success'])
        self.assertEqual(s['utility'],1)

    def test_attacker_success_not_complemented(self):
        s = summarize([{'utility':True,'security':True},{'utility':True,'security':False}], 'attack')
        self.assertEqual(s['attack_success'],.5)
        self.assertEqual(s['safe_completion'],.5)
        self.assertEqual(s['utility'],1)

    def test_only_prespecified_attack_is_selected(self):
        base = {'user_task_id':'user_task_0','injection_task_id':'injection_task_0','attack_type':'important_instructions'}
        self.assertEqual(classify(base),'attack')
        self.assertIsNone(classify({**base,'attack_type':'other'}))
        self.assertIsNone(classify({**base,'user_task_id':'injection_task_0'}))


if __name__ == '__main__':
    unittest.main()
