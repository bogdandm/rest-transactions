import socket as socket_lib
from typing import Tuple

from tools.gevent import g_async


def receive(socket: socket_lib.SocketType, block=1024):
	res = b""
	while True:
		b = socket.recv(block)
		res += b
		if not b or b"\0" in b:
			return res


class ClientConnection:
	def __init__(self, addr: Tuple[str, int]):
		self.soc = socket_lib.socket()
		self.soc.connect(addr)

	def request(self, data: bytes):
		self.soc.sendall(data)
		return receive(self.soc, 2 ** 10 * 8)


class ServerConnection:
	def __init__(self, socket: socket_lib.SocketType, addr, map_function):
		self.soc = socket
		self.addr = addr
		self.__map_function = map_function

	@g_async
	def handle(self):
		while True:
			try:
				data = receive(self.soc)
				self.soc.sendall(self.__map_function(data))
			except:
				print("Connection breaks")
				break

