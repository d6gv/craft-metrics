"""Unit tests for influx.py retry behavior — no real InfluxDB required."""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import requests

    import influx

    REQUESTS_AVAILABLE = True
except ModuleNotFoundError:
    # `requests` is a runtime dependency installed in the container; skip these tests when it
    # isn't present (e.g. running the suite on a bare host that only has the standard library).
    REQUESTS_AVAILABLE = False


def make_response(status_code):
    response = mock.Mock()
    response.status_code = status_code
    response.text = "body"
    return response


@unittest.skipUnless(REQUESTS_AVAILABLE, "requests is not installed")
class WriteLinesTests(unittest.TestCase):
    def test_no_request_when_no_lines(self):
        with mock.patch("influx.requests.post") as post:
            influx.write_lines([], "http://x", "org", "bucket", "token")
            post.assert_not_called()

    def test_success_on_first_attempt(self):
        with mock.patch("influx.requests.post", return_value=make_response(204)) as post:
            influx.write_lines(["m v=1i 1"], "http://x", "org", "bucket", "token")
            self.assertEqual(post.call_count, 1)

    def test_4xx_is_not_retried(self):
        with mock.patch("influx.requests.post", return_value=make_response(401)) as post, \
                mock.patch("influx.time.sleep"):
            with self.assertRaises(RuntimeError):
                influx.write_lines(["m v=1i 1"], "http://x", "org", "bucket", "token")
            self.assertEqual(post.call_count, 1)

    def test_5xx_is_retried_until_exhausted(self):
        with mock.patch("influx.requests.post", return_value=make_response(503)) as post, \
                mock.patch("influx.time.sleep"):
            with self.assertRaises(RuntimeError):
                influx.write_lines(["m v=1i 1"], "http://x", "org", "bucket", "token", retries=3)
            self.assertEqual(post.call_count, 3)

    def test_network_error_is_retried_then_succeeds(self):
        responses = [requests.ConnectionError("boom"), make_response(204)]

        def side_effect(*args, **kwargs):
            result = responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with mock.patch("influx.requests.post", side_effect=side_effect) as post, \
                mock.patch("influx.time.sleep"):
            influx.write_lines(["m v=1i 1"], "http://x", "org", "bucket", "token", retries=3)
            self.assertEqual(post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
