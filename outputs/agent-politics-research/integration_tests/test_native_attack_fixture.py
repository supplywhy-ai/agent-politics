import json
from pathlib import Path
import unittest
from deepdiff import DeepDiff
from agentdojo.task_suite import get_suite
from agentdojo.functions_runtime import FunctionsRuntime


class NativeAttackFixtureTests(unittest.TestCase):
    def test_only_calendar_description_changes_and_payload_reaches_tool(self):
        root=Path(__file__).resolve().parents[1]
        fixture=json.loads((root/'fixtures/native-calendar-attacks-v1.json').read_text())
        suite=get_suite('v1','workspace')
        baseline=suite.load_and_inject_default_environment({})
        for a in fixture['attacks']:
            with self.subTest(attack=a['name']):
                poisoned=suite.load_and_inject_default_environment(a['injections'])
                diff=DeepDiff(baseline.model_dump(mode='json'),poisoned.model_dump(mode='json'))
                self.assertEqual(set(diff),{'values_changed'})
                for path in diff['values_changed']:
                    self.assertTrue(path.startswith("root['calendar']"))
                    self.assertTrue(path.endswith("['description']"))
                output,error=FunctionsRuntime(suite.tools).run_function(poisoned,'search_calendar_events',
                    {'query':'Networking event','date':'2024-05-26'})
                self.assertIsNone(error)
                payload=next(iter(a['injections'].values()))
                # The benchmark's YAML loader folds literal newlines in this
                # quoted description. Verify delivered text after whitespace
                # normalization; raw and delivered forms remain in artifacts.
                self.assertTrue(any(' '.join(payload.split()) in ' '.join(e.description.split()) for e in output))
                self.assertFalse(suite.injection_tasks[fixture['injection_task']].security('',poisoned,poisoned))


if __name__=='__main__':
    unittest.main()
