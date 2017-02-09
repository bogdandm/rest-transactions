import socket
from abc import ABCMeta, abstractmethod
from typing import Tuple, Optional, Union

from gevent import monkey
from gevent.hub import ConcurrentObjectUseError

from tools.socket_ import receive, Request, Response

monkey.patch_all()


class ATcpClient(metaclass=ABCMeta):
	@abstractmethod
	def __init__(self, address: Tuple[str, int]):
		pass

	@abstractmethod
	def call(self, method: str, data: dict = None) -> Response:
		pass

	@abstractmethod
	def close(self):
		pass


class TcpClient(socket.SocketType, ATcpClient):
	def __init__(self, address: Tuple[str, int], *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.address = address
		try:
			self.connect(self.address)
			self.connected = True
		except ConnectionError:
			self.connected = False


	def call(self, method: str, data: dict = None) -> Response:
		if not self.connected:
			self.connect(self.address)
			self.connected = True
		try:
			self.sendall(Request(method, data).encode())
			raw = receive(self, 2 ** 10 * 8)
		except ConcurrentObjectUseError as e:
			print("You probably should use TcpClientThreading instead TcpClient")
			raise e
		return Response.decode(raw)


class TcpClientThreading(ATcpClient):
	def __init__(self, address: Tuple[str, int]):
		super().__init__(address)
		self.address = address

	def call(self, method: str, data: dict = None) -> Response:
		with socket.socket() as soc:
			soc.connect(self.address)
			soc.sendall(Request(method, data).encode())
			raw = receive(soc, 2 ** 10 * 8)
		return Response.decode(raw)

	def close(self):
		pass