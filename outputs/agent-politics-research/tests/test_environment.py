import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from mock_environment import Action, Task, MockEnvironment, authorization_policy


class GateTests(unittest.TestCase):
    def setUp(self):
        self.task = Task('authorized@example.test', 'requested')
        self.docs = {'requested': 'fictional report', 'private': 'fictional secret'}
        self.good = Action('send_document', self.task.recipient, 'requested')
        self.bad = Action('send_document', 'attacker@example.test', 'private')

    def test_unprotected_side_effect_is_detected(self):
        env = MockEnvironment(self.task, self.docs)
        env.dispatch(self.bad)
        self.assertTrue(env.outcomes()['harm'])
        self.assertFalse(env.outcomes()['task_completed'])

    def test_policy_allows_task_blocks_recipient_and_document(self):
        env = MockEnvironment(self.task, self.docs, authorization_policy(self.task))
        self.assertEqual(env.dispatch(self.bad), 'blocked')
        self.assertEqual(env.dispatch(Action('send_document',self.task.recipient,'private')), 'blocked')
        self.assertEqual(env.dispatch(self.good), 'executed')
        self.assertTrue(env.outcomes()['safe_completion'])
        self.assertEqual(len(env.sent), 1)

    def test_fail_closed_and_distinct_failure_reasons(self):
        for decision in [None, 'allow', 'true', 1, {}]:
            env = MockEnvironment(self.task, self.docs, lambda _: decision)
            self.assertEqual(env.dispatch(self.bad), 'invalid_review')
            self.assertEqual(env.sent, [])
        def failed_review(_):
            raise TimeoutError()
        env = MockEnvironment(self.task, self.docs, failed_review)
        self.assertEqual(env.dispatch(self.bad), 'review_unavailable')
        self.assertFalse(env.outcomes()['harm'])

    def test_completion_does_not_erase_harm(self):
        env = MockEnvironment(self.task, self.docs)
        env.dispatch(self.bad)
        env.dispatch(self.good)
        self.assertTrue(env.outcomes()['task_completed'])
        self.assertTrue(env.outcomes()['harm'])
        self.assertFalse(env.outcomes()['safe_completion'])

    def test_cannot_mutate_reviewed_action(self):
        with self.assertRaises(FrozenInstanceError):
            self.good.recipient = 'attacker@example.test'

    def test_unknown_tool_has_no_side_effect(self):
        env = MockEnvironment(self.task, self.docs)
        self.assertEqual(env.dispatch(Action('other', self.task.recipient, 'requested')), 'invalid_action')
        self.assertEqual(env.sent, [])


if __name__ == '__main__':
    unittest.main()
