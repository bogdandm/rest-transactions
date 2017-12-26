from random import choice

import gevent

from tools import timeit
from tools.gevent import g_async
from tools.socket.tcp_client import TcpClient

n_sockets = 500
n_repeats = 200


@g_async
def spawn():
	client = TcpClient(("127.0.0.1", 5000))
	for _ in range(n_repeats):
		client.call("random")
	client.close()


@timeit
def run():
	gevent.joinall([spawn() for _ in range(n_sockets)])


run()
print("Count: {}".format(n_sockets * n_repeats))
