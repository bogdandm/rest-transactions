import json
import logging.config
import socket
from typing import Tuple, Dict, Callable, Any, Union

import pathlib
from gevent.event import Event
from gevent.queue import Queue

from tools.gevent_ import g_async
from tools.socket_ import receive, Tcp500, Tcp404, Request, Response

HandlerType = Callable[[dict], Tuple[Union[str, int], Any]]

try:
	with open("tcp_logging.json") as config:
		logging.config.dictConfig(json.load(config))
except FileNotFoundError:
	path = pathlib.Path(__file__) / ".." / "tcp_logging.json"
	with open(str(path.resolve())) as config:
		logging.config.dictConfig(json.load(config))


Logger = logging.getLogger("TcpServer")
logging.info("Logger was inited")

class TcpServer:
	def __init__(self, address: Tuple[str, int], max_connections=100):
		self.socket = socket.socket()
		self.socket.bind(address)
		self.max_connections = max_connections
		self.__stop = Event()
		self.response_queue = Queue()
		self.methods_map = {}  # type: Dict[str, HandlerType]

	def run(self):
		self.socket.listen(self.max_connections)
		while not self.__stop.ready():
			clientsocket, address = self.socket.accept()  # BLOCK
			self._handler(clientsocket, address)  # THREAD:1, loop

	def stop(self):
		self.__stop.set()

	def method(self, f: HandlerType):
		"""
		Decorator. Create TCP method called same as handler function
		:param f:
		:return:
		"""
		if f.__name__ not in self.methods_map:
			self.methods_map[f.__name__] = f
		else:
			raise NameError
		return f

	@staticmethod
	def log(method: str, status: str, msg: str, level: str):
		s = "{:20s} | {:5s} | {}".format(method, status, msg)
		logging.log(logging.getLevelName(level), s)

	@g_async
	def _handler(self, socket_obj, address):
		while not self.__stop.ready():
			try:
				raw = receive(socket_obj)  # BLOCK
			except OSError as _:
				TcpServer.log("?", "?", "Call failed", "WARNING")
				return
			if not raw:
				TcpServer.log("?", "?", "Call failed", "WARNING")
				return

			try:
				method, json = Request.decode(raw).values
			except Tcp500 as e:
				try:
					method, *_ = str(raw[:-1], encoding="utf-8").split("\n", 1)
				except Exception:
					method = str(None)
				TcpServer.log(method, "500", str(e.args), "WARNING")
				socket_obj.sendall(Response(e.status, e).encode())
				return

			if method not in self.methods_map:
				e = Tcp404("method not found")
				TcpServer.log(method, "500", "Method not found", "WARNING")
				socket_obj.sendall(Response(e.status, e).encode())
				return

			try:
				resp = self.methods_map[method](json)
				TcpServer.log(method, "200", "", "INFO")
			except Exception as e:
				TcpServer.log(method, "500", str(e.args), "WARNING")
				resp = Response(500, "Fail")
			else:
				if type(resp) is tuple:
					resp = Response(*resp)
			socket_obj.sendall(resp.encode())
