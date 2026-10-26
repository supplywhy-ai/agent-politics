import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from agentdojo_local_live import review_policy,REVIEW_POLICY


class ReviewRoleTests(unittest.TestCase):
    def test_only_role_sentence_differs(self):
        self_role=review_policy('self_full')
        self.assertEqual(self_role.split('. ',1)[1],REVIEW_POLICY.split('. ',1)[1])
        self.assertEqual(review_policy('full'),REVIEW_POLICY)
        self.assertEqual(review_policy('minimized'),REVIEW_POLICY)


if __name__=='__main__':
    unittest.main()
