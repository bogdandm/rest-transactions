from typing import Any
from typing import Dict

from bson import ObjectId

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
			trid = ObjectId(data["id"])  # type: str
			if trid not in self.transactions:
				return 404, {str(trid): None}
			tr = self.transactions[trid]
			status = {}
			for k, v in tr.status.items():
				status[k] = v.name
			return 200, {str(trid): status}

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


def main(no_sse=False):
	global _debug_thread
	if not no_sse:
		_debug_thread = debug_SSE.spawn(("localhost", 9000))

	Transaction.set_self_url("http://localhost:5000/api/alpha/transactions")  # TODO: Sent from REST Service
	daemon = Daemon(("127.0.0.1", 5600))
	daemon.run()


if __name__ == '__main__':
	main()
