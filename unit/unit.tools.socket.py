from random import randint
from typing import Tuple
from unittest import TestCase

import gevent

from tools import timeit
from tools.gevent_ import g_async
from tools.socket_ import Tcp404
from tools.socket_.tcp_client import TcpClient
from tools.socket_.tcp_server import TcpServer


class Server(TcpServer):
	def __init__(self, address: Tuple[str, int]):
		super().__init__(address)
		self.db = {chr(ord('a') + i): i for i in range(ord('z') - ord('a') + 1)}

		@self.method
		def get(data):
			ch = data['ch']
			if ch in self.db:
				return 200, {"ch": ch, "ord": self.db[ch]}
			else:
				raise Tcp404(ch)

		@self.method
		def post(data):
			self.db = {**self.db, **data}
			return 200, self.db


class SocketClientServerTest(TestCase):
	server = None  # type: Server
	thread = None  # type: gevent.Greenlet
	client = None  # type: TcpClient

	@classmethod
	def setUpClass(cls):
		cls.server = Server(("127.0.0.1", 5000))
		cls.thread = gevent.spawn(lambda: cls.server.run())
		cls.client = TcpClient(("127.0.0.1", 5000))

	@classmethod
	def tearDownClass(cls):
		cls.client.close()
		cls.thread.kill()
		cls.server.stop()

	def test_get(self):
		rv = self.client.call("get", {"ch": 'b'}).values
		self.assertEqual(rv[0], '200')
		self.assertDictEqual(rv[1], {"ch": 'b', "ord": 1})

	def test_post(self):
		rv = self.client.call("post", {"_": -1}).values
		self.assertEqual(rv[0], '200')
		rv = self.client.call("get", {"ch": '_'}).values
		self.assertEqual(rv[0], '200')
		self.assertDictEqual(rv[1], {"ch": '_', "ord": -1})

	def test_spam(self):
		n_sockets = 10
		n_repeats = 100

		fails = []

		@g_async
		def spawn():
			client = TcpClient(("127.0.0.1", 5000))
			for _ in range(n_repeats):
				rv = client.call("get", {"ch": chr(randint(ord('a'), ord('z')))})
				if rv.values[0] != '200':
					fails.append(rv)
			client.close()

		@timeit
		def run():
			gevent.joinall([spawn() for _ in range(n_sockets)])

		run()
		self.assertFalse(fails, fails)
