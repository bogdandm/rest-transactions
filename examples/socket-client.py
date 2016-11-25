from random import choice

import gevent

from tools import timeit
from tools.gevent_ import g_async
from tools.socket_.tcp_client import TcpClient

WORDS = open("etc/words.txt").read().splitlines()

n_sockets = 500
n_repeats = 200


@g_async
def spawn():
	global WORDS
	client = TcpClient(("127.0.0.1", 5000))
	name = choice(WORDS)
	for _ in range(n_repeats):
		header, js = client.call("random").values
		# print("{}: ({}) {}".format(name, header, js["random"]))
	client.close()


@timeit
def run():
	gevent.joinall([spawn() for _ in range(n_sockets)])


run()
print("Count: {}".format(n_sockets * n_repeats))
