from random import randint
from typing import Tuple
from unittest import SkipTest
from unittest import TestCase

import gevent

from tools import timeit
from tools.gevent_ import g_async
from tools.socket_ import Tcp404
from tools.socket_.tcp_client import TcpClient, TcpClientThreading
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
	client_class = TcpClient
	addr = 5123

	@classmethod
	def setUpClass(cls):
		cls.server = Server(("127.0.0.1", cls.addr))
		cls.thread = gevent.spawn(lambda: cls.server.run())
		cls.client = cls.client_class(("127.0.0.1", cls.addr))

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
			client = self.client_class(("127.0.0.1", self.addr))
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

	def test_spam_single_client(self):
		if self.__class__ is SocketClientServerTest:
			raise SkipTest()
		n_sockets = 10
		n_repeats = 100

		fails = []

		client = self.client

		@g_async
		def spawn():
			for _ in range(n_repeats):
				rv = client.call("get", {"ch": chr(randint(ord('a'), ord('z')))})
				if isinstance(rv, Exception) or rv.values[0] != '200':
					fails.append(rv)

		@timeit
		def run():
			gevent.joinall([spawn() for _ in range(n_sockets)], timeout=20)

		run()
		client.close()
		self.assertFalse(fails, fails)


class SocketClientServerTestThreading(SocketClientServerTest):
	client_class = TcpClientThreading
	addr = 5124
