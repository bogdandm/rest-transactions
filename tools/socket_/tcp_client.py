import socket
from typing import Tuple
from gevent import monkey

from tools.socket_ import receive, Request, Response

monkey.patch_all()


class TcpClient(socket.SocketType):
	def __init__(self, address: Tuple[str, int], *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.connect(address)

	def call(self, method: str, data: dict = None) -> Response:
		self.sendall(Request(method, data).encode())
		raw = receive(self, 2 ** 10 * 8)
		return Response.decode(raw)
