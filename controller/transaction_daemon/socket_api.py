import json

from bson import ObjectId

from controller.transaction_daemon.transaction_backend import Transaction, TransactionManager
from tools import debug_SSE
from tools.socket_.tcp_server import TcpServer


class Daemon(TcpServer):
	def __init__(self, address=("127.0.0.1", 5000), db=None, *args, **kwargs):
		super().__init__(address, *args, **kwargs)
		self.transactions = TransactionManager(db)

		@self.method
		def open_transaction(data):
			tr = self.transactions.create(data)
			return 200, {"ID": str(tr.id)}

		@self.method
		def get_transaction(data):
			trid = ObjectId(data["id"])
			tr = self.transactions[trid]
			if not tr:
				return 404, {str(trid): None}

			if isinstance(tr, Transaction):
				status = tr.status
			else:
				status = tr["status"]
				if status:
					status = json.loads(tr["status"])
				else:
					status = "FAIL" if tr["fail"] else ("COMPLETE" if tr["complete"] else "UNKNOWN")

			return 200, {str(trid): status}

		@self.method
		def set_result(data):
			trid = ObjectId(data['id'])
			tr = self.transactions[trid]
			if not isinstance(tr, Transaction):
				return 404, {"ID": str(tr.id)}

			tr.childes[data["key"]].response.set(data["response"])
			return 200, {"ID": str(tr.id)}

		@self.method
		def set_done(data):
			trid = ObjectId(data['id'])
			tr = self.transactions[trid]
			if not isinstance(tr, Transaction):
				return 404, {"ID": str(trid)}

			tr_ch = tr.childes[data["key"]]
			if data["done"]:
				tr_ch.done.set()
			return 200, {"ID": str(tr.id)}


def main(args=None):
	import argparse
	global _debug_thread

	parser = argparse.ArgumentParser(description='Controller API TCP Service')
	parser.add_argument("--no_log", default=False, action="store_true")
	parser.add_argument("--no_sse", default=False, action="store_true")
	parser.add_argument("--db", default=":memory:", type=str)
	parser.add_argument("-p", "--port", default=5600, type=int)

	if args:
		args, _ = parser.parse_known_args(args)
	else:
		args, _ = parser.parse_known_args()

	if not args.no_sse:
		_debug_thread = debug_SSE.spawn(("localhost", 9000))

	Transaction.set_self_url("http://localhost:5000/api/alpha/transactions")  # TODO: Sent from REST Service
	daemon: Daemon = Daemon(("127.0.0.1", args.port), args.db)
	if args.no_log:
		daemon.logger.disabled = True

	daemon.serve_forever()


if __name__ == '__main__':
	main()
