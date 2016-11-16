import mock
import unittest

import koji.compatrequests


class TestResponse(unittest.TestCase):

    def setUp(self):
        session = mock.MagicMock()
        response = mock.MagicMock()
        self.response = koji.compatrequests.Response(session, response)

    def tearDown(self):
        del self.response

    def test_read(self):
        self.response.response.status = 200
        data = [
            "Here's some data",
            "Here's some mooore data",
            "And look!",
            "Here's a nice block of lorem text",
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do "
            "eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut "
            "enim ad minim veniam, quis nostrud exercitation ullamco laboris "
            "nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor "
            "in reprehenderit in voluptate velit esse cillum dolore eu fugiat "
            "nulla pariatur. Excepteur sint occaecat cupidatat non proident, "
            "sunt in culpa qui officia deserunt mollit anim id est laborum.",
            "",  #eof
        ]
        self.response.response.read.side_effect = data

        result = list(self.response.iter_content(blocksize=10240))

        self.assertEqual(result, data[:-1])
        rcalls = [mock.call(10240) for s in data]
        self.response.response.read.assert_has_calls(rcalls)

        self.response.close()
        self.response.response.close.assert_called_once()

    def test_error(self):
        self.response.response.status = 404
        self.response.response.getheader.return_value = 0
        with self.assertRaises(Exception):
            list(self.response.iter_content())
        self.response.response.read.assert_not_called()

        self.response.response.status = 404
        self.response.response.getheader.return_value = 42
        with self.assertRaises(Exception):
            list(self.response.iter_content())
        self.response.response.read.assert_called_once()
