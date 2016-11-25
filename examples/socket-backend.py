from tools.socket_.tcp_server import TcpServer
from random import randint

server = TcpServer(("127.0.0.1", 5000))


@server.method
def echo(data):
	print(data)
	return 200, data


@server.method
def random(data):
	return 200, {"random": randint(0, 2 ** 20)}


server.run()
