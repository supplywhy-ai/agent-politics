"""Prevent partial or duplicate token audits from validating a whole cohort."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from summarize_transfer import require_token_coverage

class TokenCoverage(unittest.TestCase):
    def test_missing_and_duplicate_receipts_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run=root/'run';episode=run/'episode';episode.mkdir(parents=True)
            records=[]
            for i in (1,2):
                path=episode/f'budget-call-{i:02d}.json';path.write_text('{}')
                records.append({'record':str(path),'computed_prompt_tokens':10,'reported_prompt_tokens':10,'equal':True})
            audit=root/'audit.json'
            def save(rows):audit.write_text(json.dumps({'records':rows,'all_equal':True,'count':len(rows)}))
            save(records);require_token_coverage(audit,[run])
            save(records[:1])
            with self.assertRaises(AssertionError):require_token_coverage(audit,[run])
            save(records+[records[0]])
            with self.assertRaises(AssertionError):require_token_coverage(audit,[run])

if __name__=='__main__':unittest.main()
