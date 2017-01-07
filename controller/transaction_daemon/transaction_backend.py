from datetime import datetime
from typing import Dict, Any

import requests as request_lib
from bson import ObjectId
from gevent import sleep
from gevent import wait

from tools import debug_SSE, MultiDict
from tools import transform_json_types
from tools.gevent_ import g_async
from tools.transactions import ATransaction

_debug_thread = debug_SSE.spawn(("localhost", 9000))


class Transaction(ATransaction):
	self_url = "http://localhost:5000/api"

	@classmethod
	def set_self_url(cls, url: str):
		cls.self_url = url

	def __init__(self, data: dict):
		"""
		>>> data = {
		... 	"timeout": "ms",  # Global timeout of whole transaction
		... 	"actions": [
		... 		{
		... 			"_id": "unique str",
		... 			"service": {
		... 				"name": "str",
		... 				"url": "uri",
		... 				"timeout": "ms"  # local timeout
		... 			},
		... 			"url": "uri + GET params",
		... 			"method": "HTTP method",
		... 			"data": {},
		... 			"headers": {},
		... 			"then": None  #TODO: Support in future versions
		... 		}
		... 		# ...
		... 	]
		... }

		:param data:
		"""
		super().__init__(ObjectId())
		debug_SSE.event({"event": "init", "t": datetime.now(), "data": data})  # DEBUG init
		self.timeout = data["timeout"] / 1000
		self.childes = MultiDict(
			{tr["_id"]: ChildTransaction(self, **tr) for tr in data["actions"]}
		)  # type: Dict[Any, ChildTransaction]

	@property
	def status(self):
		return {
			"global": super().status,
			**{ch.id: ch.status for ch in self.childes.values()}
		}

	def __repr__(self):
		return "Transaction#{}: {}".format(self.id, super().status)

	@g_async
	def _spawn(self):
		self.threads += [ch.run() for ch in self.childes.values()]  # THREAD:N, blocked
		self.__wait_child_fail(), self.__wait_childes_ready_commit()
		wait((self.ready_commit, self.fail), count=1)  # BLOCK # LISTENER
		if self.ready_commit.ready():
			debug_SSE.event({"event": "ready_commit", "t": datetime.now()})  # DEBUG ready_commit
		elif self.fail.ready():
			debug_SSE.event({"event": "fail", "t": datetime.now()})  # DEBUG fail

		pass  # killall(self.threads)  # THREAD:-?

	# TODO: commit | rollback
	@g_async
	def commit(self):
		pass  # TODO

	@g_async
	def rollback(self):
		pass  # TODO

	@g_async
	def __wait_childes_ready_commit(self):  # LISTENER
		wait([ch.ready_commit for ch in self.childes.values()])  # BLOCK
		self.ready_commit.set()  # EMIT(ready_commit)

	@g_async
	def __wait_child_fail(self):  # LISTENER
		e = wait([ch.fail for ch in self.childes.values()], count=1, timeout=self.timeout)  # BLOCK, timeout
		ch = None
		for ch in self.childes.values():
			if ch.fail.ready():
				break
		debug_SSE.event({"event": "fail_child", "t": datetime.now(), "data": ch.id if ch else None})  # DEBUG fail_child
		self.fail.set()  # EMIT(fail)


class ChildTransaction(ATransaction):
	class Service:
		def __init__(self, name, url, timeout):
			self.name = name
			self.url = url
			self.timeout = timeout / 1000

		def __repr__(self):
			return "{} <{}>".format(self.name, self.url)

	def __init__(self, parent: 'Transaction', _id: str, url: str, method: str, data: dict, headers: dict, service: dict,
				 **kwargs):
		super().__init__(_id)
		debug_SSE.event({"event": "init_child", "t": datetime.now(), "data": _id})  # DEBUG init_child
		self.parent = parent

		self.url = url
		self.method = method
		self.data = data
		self.headers = headers
		self.service = ChildTransaction.Service(**service) # type: ChildTransaction.Service

		self.remote_id = None
		self.key = None
		self.ping_timeout = -1

	@g_async
	def _spawn(self):
		try:
			resp = request_lib.post(self.service.url + "/transactions", json={
				"timeout": self.service.timeout,
				"callback-url": "{}/{}".format(self.parent.self_url, self.parent.id)
			}, timeout=self.service.timeout)  # BLOCK, timeout
		except request_lib.RequestException:
			self.fail.set()  # EMIT(fail)
			return

		if resp.status_code != 200:
			self.fail.set()  # EMIT(fail)
		else:
			js = resp.json()
			transform_json_types(js, direction=1)
			# TODO: validate

			debug_SSE.event({
				"event": "init_child_2", "t": datetime.now(),
				"data": {"chid": self.id, **js}
			})  # DEBUG init_child_2

			self.remote_id = js["_id"]
			self.key = js["transaction-key"]
			self.parent.childes[self.key] = self
			self.ping_timeout = js["ping-timeout"] / 1000

			# noinspection PyTypeChecker
			self.parent.threads.append(self.__ping())  # THREAD:1, loop
			# noinspection PyTypeChecker
			self.parent.threads.append(self.__wait_response())  # THREAD:1

	@g_async
	def __ping(self):
		while not (self.committed.ready() or self.fail.ready()):
			debug_SSE.event({"event": "ping_child", "t": datetime.now(), "data": self.id})  # DEBUG ping_child
			try:
				resp = request_lib.get(self.service.url + "/transactions/" + str(self.remote_id), headers={
					"X-Transaction": self.key
				}, timeout=self.ping_timeout)  # BLOCK, timeout
			except request_lib.RequestException:
				self.fail.set()  # EMIT(fail)
				return
			if resp.status_code != 200:
				self.fail.set()  # EMIT(fail)
				return
			t = self.ping_timeout - resp.elapsed.total_seconds()
			sleep(t)  # BLOCK, sleep
		# Max timeout ~= ping_timeout

	@g_async
	def __wait_response(self):  # LISTENER
		try:
			# TODO: Get query params test
			resp = request_lib.request(self.method, self.service.url + self.url, headers={
				"X-Transaction": self.key, **self.headers
			}, json=self.data, timeout=self.service.timeout)  # BLOCK, timeout
		except request_lib.RequestException:
			self.fail.set()  # EMIT(fail)
			return
		if resp.status_code != 200:
			self.fail.set()  # EMIT(fail)
			return

		wait((self.response,), timeout=self.service.timeout)  # BLOCK, timeout
		if self.response.successful():
			js = self.response.get()
			debug_SSE.event({
				"event": "ready_commit_child", "t": datetime.now(),
				"data": {"chid": self.id, **js}
			})  # DEBUG ready_commit_child
			self.ready_commit.set()  # EMIT(ready_commit)
			return
		self.fail.set()  # EMIT(fail)

	@g_async
	def commit(self):
		pass  # TODO

	@g_async
	def rollback(self):
		pass  # TODO
