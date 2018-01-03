import json
import logging.config
import pathlib
import socket
from abc import ABCMeta, abstractmethod
from typing import Tuple, Dict, Callable, Any, Union

from gevent import spawn
from gevent.event import Event
from gevent.server import StreamServer

from tools.socket import receive, Tcp500, Tcp404, Request, Response, ATcpException

HandlerType = Callable[[dict], Tuple[Union[str, int], Any]]

# init logger
try:
    with open("tcp_logging.json") as config:
        logging.config.dictConfig(json.load(config))
except FileNotFoundError:
    path = pathlib.Path(__file__) / ".." / "tcp_logging.json"
    with open(str(path.absolute().resolve())) as config:
        logging.config.dictConfig(json.load(config))


class AServer(metaclass=ABCMeta):
    _logger = logging.getLogger("AServer")

    @abstractmethod
    def __init__(self, address: Tuple[str, int], max_connections=100):
        self.max_connections = max_connections
        self.methods_map = {}  # type: Dict[str, HandlerType]
        self._stop = Event()

    @abstractmethod
    def serve_forever(self):
        pass

    def stop(self):
        self._stop.set()

    def method(self, f: HandlerType):
        """
        Decorator. Create TCP method called same as handler function
        :param f:
        :return:
        """
        if f.__name__ not in self.methods_map:
            self.methods_map[f.__name__] = f
        else:
            raise NameError(f.__name__)
        return f

    def _handler(self, socket_obj: socket.SocketType, address: Tuple[str, int]):
        while not self._stop.ready():
            try:
                raw = receive(socket_obj)  # BLOCK
            except OSError as e:
                self.log("?", e, "Call failed", "WARNING")
                return
            if not raw:
                return

            try:
                method, json = Request.decode(raw).values
            except Tcp500 as e:
                try:
                    method, _ = str(raw[:-1], encoding="utf-8").split("\n", 1)
                except:
                    method = str(None)
                self.log(method, "500", str(e.args), "WARNING")
                socket_obj.sendall(Response(e.status, e).encode())
                return

            if method not in self.methods_map:
                e = Tcp404("method not found")
                self.log(method, "404", "Method not found", "WARNING")
                socket_obj.sendall(Response(e.status, e).encode())
                return

            try:
                resp = self.methods_map[method](json)
                self.log(method, "200", "", "INFO")
            except ATcpException as e:
                self.log(method, str(e.status), str(e.args), "WARNING")
                resp = Response(e.status, e.text)
            except Exception as e:
                self.log(method, "500", str(e.args), "WARNING")
                resp = Response(500, "Fail")
            else:
                if type(resp) is tuple:
                    resp = Response(*resp)
            socket_obj.sendall(resp.encode())

    @property
    def logger(self):
        return self._logger

    def log(self, method: str, status: Union[str, Exception], msg: str, level: str):
        s = f"{method:20s} | {status:5s} | {msg}"
        self.logger.log(logging.getLevelName(level), s)


class TcpServer(AServer):
    _logger = logging.getLogger("TcpServer")

    def __init__(self, address: Tuple[str, int], max_connections=100):
        super().__init__(address, max_connections)
        self.socket = socket.socket()
        self.socket.bind(address)

    def serve_forever(self):
        self.socket.listen(self.max_connections)
        while not self._stop.ready():
            clientsocket, address = self.socket.accept()  # BLOCK
            self._handler(clientsocket, address)  # THREAD:1, loop

    def stop(self):
        super().stop()
        self.socket.close()

    def _handler(self, socket_obj: socket.SocketType, address: Tuple[str, int]):
        spawn(super()._handler, socket_obj, address)


class GeventTcpServer(StreamServer, AServer):
    _logger = logging.getLogger("GeventTcpServer")

    def __init__(self, address: Tuple[str, int], max_connections=100, **ssl_args):
        StreamServer.__init__(self, address, handle=self._handler, **ssl_args)
        AServer.__init__(self, address, max_connections)
        self.max_accept = self.max_connections

    def stop(self, timeout=None):
        StreamServer.stop(self, timeout)
        AServer.stop(self)
