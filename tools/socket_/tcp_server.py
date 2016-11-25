import socket
from typing import Tuple

from gevent.event import Event
from gevent.queue import Queue

from tools.gevent_ import g_async
from tools.socket_ import receive, Tcp500, Tcp404, Request, Response


class TcpServer:
	def __init__(self, address: Tuple[str, int], max_connections=100):
		self.socket = socket.socket()
		self.socket.bind(address)
		self.max_connections = max_connections
		self.__stop = Event()
		self.response_queue = Queue()
		self.methods_map = {}

	def run(self):
		self.socket.listen(self.max_connections)
		while not self.__stop.ready():
			(clientsocket, address) = self.socket.accept()  # BLOCK
			self._handler(clientsocket, address)  # THREAD:1, loop

	def stop(self):
		self.__stop.set()

	# decorator
	def method(self, f):
		if f.__name__ not in self.methods_map:
			self.methods_map[f.__name__] = f
		else:
			raise NameError
		return f

	@g_async
	def _handler(self, socket_obj, address):
		while not self.__stop.ready():
			try:
				raw = receive(socket_obj)  # BLOCK
			except OSError as _:
				return
			if raw == b"":
				return

			try:
				method, body = Request.decode(raw).values
			except Tcp500 as e:
				socket_obj.sendall(Response(e.status, e).encode())
				return

			if method not in self.methods_map:
				e = Tcp404("method not found")
				socket_obj.sendall(Response(e.status, e).encode())
				return

			resp = self.methods_map[method](body)
			if type(resp) is tuple:
				resp = Response(*resp)
			socket_obj.sendall(resp.encode())
