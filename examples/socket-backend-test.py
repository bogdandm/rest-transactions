from random import randint
from typing import Tuple

import gevent

from tools import timeit
from tools.gevent_ import g_async
from tools.socket_.tcp_client import TcpClient
from tools.socket_.tcp_server import TcpServer, GeventTcpServer

address = ('localhost', 5000)
n_connetions = 100
n_requests = 100


class Server1(TcpServer):
	def __init__(self, address: Tuple[str, int]):
		super().__init__(address, max_connections=10 ** 3)
		self.logger.disabled = True

		@self.method
		def test(data):
			return 200, {"random": randint(0, 2 ** 20)}


class Server2(GeventTcpServer):
	def __init__(self, address: Tuple[str, int]):
		super().__init__(address, max_connections=10 ** 3)
		self.logger.disabled = True

		@self.method
		def test(data):
			return 200, {"random": randint(0, 2 ** 20)}


@g_async
def spawn():
	client: TcpClient = TcpClient(address)
	for _ in range(n_requests):
		__ = client.call("test").values
	gevent.sleep(1)


@timeit
def spawn_server(server):
	th = gevent.spawn(server.serve_forever)
	gevent.joinall([spawn() for _ in range(n_connetions)])
	server.stop()


if __name__ == '__main__':
	spawn_server(Server1(address))
	spawn_server(Server2(address))
