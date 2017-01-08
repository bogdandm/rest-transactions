import json as json_lib
import time
from datetime import datetime
from hashlib import sha256
from random import randint
from typing import Any
from typing import Dict

import requests
from bson import ObjectId
from flask import request
from gevent import sleep, wait
from gevent.event import Event, AsyncResult
from gevent.pywsgi import WSGIServer
from werkzeug.exceptions import NotFound

from tools import debug_SSE, MultiDict
from tools.flask_ import EmptyApp
from tools.flask_.decorators import validate, json
from tools.gevent_ import g_async
from tools.transactions import ATransaction

app = None  # type: Application

PING = (2, 5)
WORK = (10, 30)


class TransactionDummy(ATransaction):
	ping_timeout = 5  # sec
	result_timeout = 20  # sec

	def __init__(self, callback_url: str, local_timeout: int, ping_timeout=None, result_timeout=None):
		super().__init__(ObjectId())
		print(callback_url)
		self.callback_url = callback_url
		self.local_timeout = local_timeout
		self.ping_timeout = ping_timeout if ping_timeout is not None else TransactionDummy.ping_timeout
		self.result_timeout = result_timeout if result_timeout is not None else TransactionDummy.result_timeout

		self.key = sha256(bytes(
			str(self.id) + str(int(time.time() * 10 ** 6) ^ randint(0, 2 ** 20)),
			encoding="utf-8"
		)).hexdigest()

		debug_SSE.event({"event": "init", "t": datetime.now(), "data": {
			"callback_url": self.callback_url,
			"local_timeout": self.local_timeout * 1000,
			"result_timeout": self.result_timeout * 1000,
			"ping_timeout": self.ping_timeout * 1000,
			"key": self.key,
			"_id": self.id
		}})  # DEBUG init

		self._ping = Event()
		self.result = AsyncResult()
		self.ping_timeout_thread_obj = None
		self.result_thread_obj = None

	@g_async
	def _spawn(self):
		self.ping_timeout_thread_obj = self.ping_timeout_thread()  # THREAD:1, loop

		wait((self.ready_commit, self.fail), timeout=self.local_timeout)  # BLOCK, timeout
		wait((self.committed, self.fail))  # BLOCK

	@g_async
	def ping_timeout_thread(self):
		while not (self.committed.ready() or self.fail.ready()):
			debug_SSE.event({"event": "wait_ping", "t": datetime.now(), "data": None})  # DEBUG wait_ping
			w = wait((self._ping, self.committed, self.fail),
					 timeout=self.ping_timeout * 2, count=1)  # BLOCK, timeout
			if not len(w):
				debug_SSE.event({"event": "fail", "t": datetime.now(), "data": "ping timeout"})  # DEBUG ping timeout
				self.fail.set()  # EMIT(fail)
				break

			if self._ping.ready():
				debug_SSE.event({"event": "ping", "t": datetime.now(), "data": None})  # DEBUG ping
				self._ping.clear()  # EMIT(-ping)
				sleep()

	def do_work(self, resource):
		self.result_thread_obj = self.result_thread(resource)  # THREAD:1

	@g_async
	def result_thread(self, resource):
		sleep(self.result_timeout)  # BLOCK, sleep
		if not (self.ready_commit.ready() or self.fail.ready()):
			global app
			self.result.set({
				"data": resource
			})  # EMIT(result)
			self.ready_commit.set()  # EMIT(ready_commit)
			debug_SSE.event({"event": "ready_commit", "t": datetime.now(), "data": None})  # DEBUG ready_commit
			data = {
				"service_name": app.name,
				"key": self.key,
				"response": self.result.get(),
				"status": "READY"
			}
			print("Result send to {}\nResult:\n{}".format(self.callback_url, json_lib.dumps(data, indent=4)))
			rp = requests.put(self.callback_url, headers={"Connection": "close"}, json=data, timeout=5)
		else:
			raise Exception("error during work")

	def ping(self, prepare=False) -> bool:
		if not (self.fail.ready() or self.committed.ready()):
			self._ping.set()  # EMIT(ping)
			if prepare:
				debug_SSE.event({"event": "prepare_commit", "t": datetime.now(), "data": None})  # DEBUG prepare_commit
				return self.ready_commit.ready()
			else:
				return True
		return False

	def commit(self):
		if not self.fail.ready():
			if self.ready_commit.ready() and self.result.ready():
				self.committed.set()  # EMIT(ping)
				debug_SSE.event({"event": "committed", "t": datetime.now(), "data": None})  # DEBUG commit
			else:
				raise Exception("error during commit")

	def rollback(self):
		self.fail.set()  # EMIT(fail)
		debug_SSE.event({"event": "rollback", "t": datetime.now(), "data": None})  # DEBUG rollback


class Application(EmptyApp):
	def __init__(self, root_path, app_root, name="Service Dummy", debug=True):
		super().__init__(root_path, app_root, extended_errors=debug)
		self.name = name
		self.transactions = MultiDict()  # type: Dict[Any, TransactionDummy]

		@self.route("/transactions", methods=["POST"])
		@validate(self.schemas["transaction_post"])
		@json(id_field="_id")
		def transaction_post(data):
			tr = TransactionDummy(data["callback-url"], data["timeout"] / 1000, randint(*PING), randint(*WORK))
			tr.run()  # THREAD:root
			self.transactions[str(tr.id)] = tr
			self.transactions[tr.key] = tr
			return {
				"service-name": self.name,
				"_id": str(tr.id),
				"transaction-key": tr.key,
				"ping-timeout": tr.ping_timeout * 1000
			}

		@self.route("/transactions/<trid>", methods=["GET"])
		@json()
		# PING
		def transaction_id_get(trid):
			tr = self.transactions.get(trid)
			key = request.headers["X-Transaction"]
			if tr is None or tr.key != key:
				raise NotFound
			return {"alive": tr.ping("prepare" in request.args)}

		@self.route("/transactions/<trid>", methods=["POST"])
		@json()
		# COMMIT
		def transaction_id_post(trid):
			tr = self.transactions.get(trid)
			key = request.headers["X-Transaction"]
			if tr is None or tr.key != key:
				raise NotFound
			tr.commit()
			return {"OK": tr.committed.ready()}

		@self.route("/transactions/<trid>", methods=["DELETE"])
		@json()
		# ROLLBACK
		def transaction_id_delete(trid):
			tr = self.transactions.get(trid)
			key = request.headers["X-Transaction"]
			if tr is None or tr.key != key:
				raise NotFound
			tr.rollback()
			return {"OK": tr.fail.ready()}

		@self.route("/<any_resource>", methods=["GET", "POST", "PUT", "DELETE"])
		@json()
		def any_route(any_resource):
			debug_SSE.event({"event": "touch", "t": datetime.now(), "data": any_resource})  # DEBUG touch
			key = request.headers["X-Transaction"]
			tr = self.transactions.get(key)
			if tr is None:
				raise NotFound
			tr.do_work(any_resource)

			return {
				"transaction": {
					"key": key,
					"status": tr.status
				}
			}


if __name__ == '__main__':
	import argparse

	parser = argparse.ArgumentParser(description='Transaction API REST Service')
	parser.add_argument("-n", "--number", default=0, type=int)
	parser.add_argument("-d", "--debug", default=0, action="store_true")
	args, _ = parser.parse_known_args()
	n, debug = args.number, args.debug

	_debug_thread = debug_SSE.spawn(("localhost", 9010 + n))
	app = Application("./", "/api", "Service #" + str(n), debug=debug)  # type: Application
	http_server = WSGIServer(('localhost', 5010 + n), app)
	http_server.serve_forever()
