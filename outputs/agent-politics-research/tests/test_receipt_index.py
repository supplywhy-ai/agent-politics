from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from analyze_local_development import index_receipts
from study_prompts import digest


class ReceiptTests(unittest.TestCase):
    def test_same_request_in_two_stages_retains_both_receipts(self):
        rec={'request_id':'same','origin':'model_recording','text':'{"allow":true}'}
        a={'request_id':'same','response_sha256':digest(rec),'elapsed_seconds':1}
        b={**a,'elapsed_seconds':2}
        stages=(('reviews',[rec]),('probes',[rec]))
        result=index_receipts([a,b],stages)
        self.assertEqual(result[('reviews','same')]['elapsed_seconds'],1)
        self.assertEqual(result[('probes','same')]['elapsed_seconds'],2)
        with self.assertRaises(AssertionError):
            index_receipts([{**a,'response_sha256':'tampered'},b],stages)


if __name__=='__main__':
    unittest.main()
