"""A request that gets no answer within the timeout is sent again; only a timeout is sent again; every AI path follows the same rule."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from ergo import ai_config as config
from ergo.gpt import client, intake, client_pool
from ergo.vision import client as vision_client
from tests.test_v2_gpt import summary_fixture


class APITimeoutError(Exception):
    """Same class name as the SDK's; the rule (and the reason mapping) look at the name only."""


class ServerBusy(Exception):
    """Any error that is not a timeout."""


def completed(data=None):
    return SimpleNamespace(id='resp_ok', status='completed', model='m', reasoning=SimpleNamespace(effort='high'),
                           output_text=json.dumps(data if data is not None else dict(answers=[], questions=[])))


class RequestResend(unittest.TestCase):
    def setUp(self):
        client_pool.close_clients()
        self.settings = config.values(dict(gpt_model='m'))

    def tearDown(self):
        client_pool.close_clients()

    def feed(self, outcomes):
        """One outcome per send: an exception is raised, anything else is returned. The last outcome repeats."""
        sends = []

        def create(**kwargs):
            sends.append(kwargs)
            outcome = outcomes[min(len(sends) - 1, len(outcomes) - 1)]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        return sends, create

    def adaptive(self, create):
        with patch('openai.OpenAI') as factory:
            factory.return_value.responses.create.side_effect = create
            return intake.request({}, {}, 'm', 'k', self.settings)

    def test_policy_is_120_seconds_per_send_three_sends_and_the_sdk_does_not_retry(self):
        self.assertEqual((config.REQUEST_TIMEOUT_SECONDS, config.REQUEST_ATTEMPTS), (120.0, 3))
        with patch('openai.OpenAI') as factory:
            client_pool.get_client('policy-key')
        self.assertEqual(factory.call_args.kwargs, dict(api_key='policy-key', timeout=120.0, max_retries=0))

    def test_a_timeout_is_sent_again_with_the_same_input_and_the_late_answer_is_used(self):
        sends, create = self.feed([APITimeoutError('no answer'), completed()])
        raw, reason = self.adaptive(create)
        self.assertIsNone(reason)
        self.assertEqual(raw['_connection']['response_id'], 'resp_ok')
        self.assertEqual(len(sends), 2)
        self.assertEqual(sends[0], sends[1], 'the same request, not a changed one')

    def test_two_timeouts_in_a_row_still_end_with_the_third_send(self):
        sends, create = self.feed([APITimeoutError('1'), APITimeoutError('2'), completed()])
        raw, reason = self.adaptive(create)
        self.assertIsNone(reason)
        self.assertEqual(len(sends), 3)

    def test_after_the_attempt_limit_every_ai_path_reports_timeout(self):
        calls = dict(
            adaptive=lambda: intake.request({}, {}, 'm', 'k', self.settings),
            interpret=lambda: client.interpret('진술', [], {}, 'm', 'k', self.settings),
            explanation=lambda: client.generate(summary_fixture(), 'm', 'k', self.settings),
            photo=lambda: vision_client.observe('data:image/jpeg;base64,AAEC', {}, 'm', 'k', self.settings))
        for name, call in calls.items():
            with self.subTest(path=name):
                sends, create = self.feed([APITimeoutError('no answer')])
                with patch('openai.OpenAI') as factory:
                    factory.return_value.responses.create.side_effect = create
                    result, reason = call()
                self.assertIsNone(result)
                self.assertEqual(reason, 'TIMEOUT')
                self.assertEqual(len(sends), config.REQUEST_ATTEMPTS, 'sent again until the limit, not forever and not once')
                client_pool.close_clients()

    def test_only_a_timeout_is_sent_again(self):
        sends, create = self.feed([ServerBusy('503')])
        raw, reason = self.adaptive(create)
        self.assertIsNone(raw)
        self.assertEqual(reason, 'API_ERROR')
        self.assertEqual(len(sends), 1, 'an error that is not a timeout is never repeated')

    def test_a_timeout_then_another_error_stops_at_that_error(self):
        sends, create = self.feed([APITimeoutError('no answer'), ServerBusy('503'), completed()])
        raw, reason = self.adaptive(create)
        self.assertEqual(reason, 'API_ERROR')
        self.assertEqual(len(sends), 2)

    def test_an_answer_that_is_not_complete_is_not_a_timeout_and_is_not_sent_again(self):
        unfinished = SimpleNamespace(id='r', status='incomplete', model='m', output_text='')
        sends, create = self.feed([unfinished, completed()])
        raw, reason = self.adaptive(create)
        self.assertEqual(reason, 'INCOMPLETE_RESPONSE')
        self.assertEqual(len(sends), 1)


if __name__ == '__main__':
    unittest.main()
