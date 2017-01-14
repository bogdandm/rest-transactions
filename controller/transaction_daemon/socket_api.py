from datetime import datetime
from typing import Any
from typing import Dict

from bson import ObjectId
from gevent import wait

from controller.transaction_daemon.transaction_backend import Transaction
from tools import MultiDict
from tools import debug_SSE
from tools.socket_.tcp_server import TcpServer


class Daemon(TcpServer):
	def __init__(self, address=("127.0.0.1", 5000)):
		super().__init__(address)
		self.transactions = MultiDict()  # type: Dict[Any, Transaction]

		@self.method
		def open_transaction(data):
			tr = Transaction(data)
			self.transactions[tr.id] = tr
			tr.run()  # THREAD:1
			return 200, {"ID": str(tr.id)}

		@self.method
		def get_transaction(data):
			trid = data["id"]  # type: str
			tr = self.transactions[ObjectId(trid)]
			return 200, {trid: tr.status}

		@self.method
		def set_result(data):
			_id = ObjectId(data['id'])
			tr = self.transactions[_id]
			tr_ch = tr.childes[data["key"]]
			tr_ch.response.set(data["response"])
			return 200, {"ID": str(tr.id)}

		@self.method
		def set_done(data):
			_id = ObjectId(data['id'])
			tr = self.transactions[_id]
			tr_ch = tr.childes[data["key"]]
			if data["done"]:
				tr_ch.done.set()
			return 200, {"ID": str(tr.id)}


if __name__ == '__main__':
	Transaction.set_self_url("http://localhost:5000/api/alpha/transactions")  # TODO: Sent from REST Service
	daemon = Daemon(("127.0.0.1", 5600))
	daemon.run()
