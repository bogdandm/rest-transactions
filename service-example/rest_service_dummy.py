import time
from hashlib import sha256
from random import randint

import requests
from bson import ObjectId
from flask import request
from gevent import sleep, wait
from gevent.event import Event, AsyncResult
from werkzeug.exceptions import NotFound

from tools.flask_ import EmptyApp
from tools.flask_.decorators import validate, json
from tools.gevent_ import g_async
from tools.transactions import EStatus


class Transaction:
	ping_timeout = 60  # sec

	def __init__(self, callback: str, timeout: int):
		self.callback = callback
		self.timeout = timeout * 1000
		self.id = ObjectId()
		self.key = sha256(bytes(
			str(self.id) + str(int(time.time() * 10 ** 6) ^ randint(0, 2 ** 20)),
			encoding="utf-8"
		)).hexdigest()
		self.finish = Event()
		self.fail = Event()
		self.__ping = Event()

		self.spawn(),  # THREAD:1, block
		self.ping_timeout_thread = self.ping_timeout_loop()  # THREAD:1, loop, block
		self.result = AsyncResult()
		self.result_thread()  # THREAD:1, sleep

	@property
	def status(self):
		m = {
			(False, False): EStatus.IN_PROGRESS,
			(False, True): EStatus.FAIL,
			(True, False): EStatus.FINISH,
			(True, True): EStatus.FAIL
		}

		def f(tr):
			return tr.finish.ready(), tr.fail.ready()

		return m[f(self)]

	@g_async
	def spawn(self):
		wait((self.finish, self.fail), timeout=self.timeout)  # BLOCK, timeout
		self.ping_timeout_thread.kill()
		if not self.finish.ready():
			print("timeout")
			if not self.fail.set():
				self.fail.set()

	@g_async
	def ping_timeout_loop(self):
		while not self.finish.ready():
			e = wait((self.__ping,), timeout=self.ping_timeout * 2)  # BLOCK, timeout
			self.__ping.clear()
			if not len(e):
				print("ping_timeout")
				self.fail.set()
				break

	@g_async
	def result_thread(self):
		sleep(1)
		if not (self.finish.ready() or self.fail.ready()):
			self.result.set({
				"data": self.key
			})
			rp = requests.put(self.callback, json={
				"service_name": Application.name,
				"key": self.key,
				"response": self.result.get(),
				"status": "READY"
			})
			print(rp)

	def commit(self):
		if not self.fail.ready():
			if self.result.ready():
				print("commit")
				self.finish.set()
			else:
				print("commit fail")
				self.fail.set()

	def rollback(self):
		self.fail.set()

	def ping(self):
		if not self.fail.ready():
			print("ping")
			self.__ping.set()
			return True
		return False


class Application(EmptyApp):
	name = "Service Dummy"

	def __init__(self, root_path, app_root):
		super().__init__(root_path, app_root)
		self.transactions = {}
		self.transactions_by_key = {}

		@self.route("/transaction", methods=["POST"])
		@validate(self.schemas["transaction_post"])
		@json
		def transaction_post(data):
			tr = Transaction(data["callback-url"], data["timeout"])
			self.transactions[str(tr.id)] = tr
			self.transactions_by_key[tr.key] = tr
			return {
				"service-name": self.name,
				"_id": tr.id,
				"transaction-key": tr.key,
				"ping-timeout": tr.ping_timeout * 1000
			}

		@self.route("/transaction/<trid>", methods=["GET"])
		@json
		# PING
		def transaction_id_get(trid):
			tr = self.transactions.get(trid)
			key = request.headers["X-Transaction"]
			if tr is None or tr.key != key:
				raise NotFound
			return {"alive": tr.ping()}

		@self.route("/transaction/<trid>", methods=["POST"])
		@json
		# COMMIT
		def transaction_id_post(trid):
			tr = self.transactions.get(trid)
			key = request.headers["X-Transaction"]
			if tr is None or tr.key != key:
				raise NotFound
			tr.commit()
			return {"OK": tr.finish.ready()}

		@self.route("/transaction/<trid>", methods=["DELETE"])
		@json
		# ROLLBACK
		def transaction_id_delete(trid):
			tr = self.transactions.get(trid)
			key = request.headers["X-Transaction"]
			if tr is None or tr.key != key:
				raise NotFound
			tr.rollback()
			return {"OK": tr.fail.ready()}

		@self.route("/<s>", methods=["GET", "POST"])
		@json
		# ROLLBACK
		def any_route(s):
			key = request.headers["X-Transaction"]
			tr = self.transactions_by_key.get(key)
			if tr is None:
				raise NotFound

			return {
				"transaction": {
					"key": key,
					"status": tr.status
				}
			}


if __name__ == '__main__':
	app = Application("./", "/api")
	app.run()
