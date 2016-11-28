from tools.socket_.tcp_server import TcpServer
from controller.transaction_daemon.transaction import Transaction


class Daemon(TcpServer):
	def __init__(self):
		super().__init__(("127.0.0.1", 5555))
		self.transactions = {}

		@self.method
		def open_transaction(data):
			tr = Transaction(data)
			self.transactions[tr.id]=tr
			tr.spawn() # THREAD:1

		@self.method
		def set_result(data):
			pass


if __name__ == '__main__':
	Transaction.set_self_url("localhost:5000")
	daemon = Daemon()
	daemon.run()
