import os
import tempfile
import unittest
import importlib
from utils import wallet_messenger

class WalletMessengerTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ['MESSAGE_DIR'] = self.tempdir.name
        importlib.reload(wallet_messenger)

    def tearDown(self):
        self.tempdir.cleanup()
        os.environ.pop('MESSAGE_DIR', None)
        importlib.reload(wallet_messenger)

    def test_send_and_read(self):
        addr = 'alice'
        from_addr = 'bob'
        subject = 'hello'
        body = 'hi alice'
        msg_id = wallet_messenger.send_message(addr, from_addr, subject, body)
        self.assertEqual(msg_id, 1)
        msgs = wallet_messenger.list_messages(addr)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]['subject'], subject)
        msg = wallet_messenger.read_message(addr, 'hello')
        self.assertEqual(msg['message'], body)

if __name__ == '__main__':
    unittest.main()
