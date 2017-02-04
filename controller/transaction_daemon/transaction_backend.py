from datetime import datetime
from typing import Dict, Any

import requests as request_lib
from bson import ObjectId
from gevent import Greenlet
from gevent import joinall
from gevent import sleep
from gevent import wait

from tools import debug_SSE, MultiDict
from tools import transform_json_types
from tools.gevent_ import g_async, Wait
from tools.transactions import ATransaction


class Transaction(ATransaction):
	done_timeout = 30  # s
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
		self.global_timeout = data["timeout"] / 1000
		self.global_timeout_thread = None  # type: Greenlet
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
		self.global_timeout_thread = self.wait_fail()

		# Phase 1

		self.threads += [ch.run() for ch in self.childes.values()]  # THREAD:N, blocked
		wait([ch.ready_commit for ch in self.childes.values()])  # BLOCK
		if not self.fail.ready():
			self.ready_commit.set()

		# Phase 2

		if self.ready_commit.ready():
			debug_SSE.event({"event": "ready_commit", "t": datetime.now()})  # DEBUG ready_commit
			debug_SSE.event({"event": "commit", "t": datetime.now()})  # DEBUG commit
			joinall([ch.do_commit() for ch in self.childes.values()])  # BLOCK  # THREAD:N

			# THREAD: 1, blocked
			done = wait(
				[ch.done for ch in self.childes.values()], count=len(self.childes), timeout=self.done_timeout
			)
			if not self.fail.ready() and len(done) == len(self.childes):
				self.done.set()  # EMIT(ready_commit)
				debug_SSE.event({"event": "finish", "t": datetime.now()})  # DEBUG finish
				joinall([ch.send_finish() for ch in self.childes.values()])
			else:
				self.fail.set()
			self.tear_down()

	@g_async
	def wait_fail(self):
		def on_child_fail(e):
			ch = next(filter(lambda ch: ch.fail.ready(), self.childes.values()), None)
			debug_SSE.event(
				{"event": "fail_child", "t": datetime.now(), "data": ch.id if ch else None})  # DEBUG fail_child
			self.fail.set()  # EMIT(fail)

		w_fail = Wait([ch.fail for ch in self.childes.values()], count=1, timeout=self.global_timeout,
					  then=on_child_fail, connect_to=self)

		e = wait((self.fail, self.done), count=1, timeout=self.global_timeout)
		if self.done.ready(): return
		self.main_thread.kill()
		self.do_rollback("global timeout" if len(e) == 0 else None)
		self.tear_down()

	def do_rollback(self, reason=None):
		debug_SSE.event({"event": "fail", "t": datetime.now(), "data": reason})  # DEBUG fail
		joinall([ch.do_rollback() for ch in self.childes.values()])  # BLOCK  # THREAD:N
		debug_SSE.event({"event": "rollback", "t": datetime.now()})  # DEBUG rollback

	@g_async
	def tear_down(self):
		self.main_thread.kill()
		self.global_timeout_thread.kill()
		for thread in self.threads:
			thread.kill()
		self.threads = []

		for w in Wait.connections[self]:
			w.kill()
		del Wait.connections[self]


class ChildTransaction(ATransaction):
	class Service:
		def __init__(self, url, timeout):
			self.url = url
			self.timeout = timeout / 1000

		def __repr__(self):
			return "<{}>".format(self.url)

	def __init__(self, parent: 'Transaction', _id: str, url: str, method: str, data: dict, headers: dict, service: dict,
				 **kwargs):
		super().__init__(_id)
		debug_SSE.event({"event": "init_child", "t": datetime.now(), "data": _id})  # DEBUG init_child
		self.parent = parent

		self.url = url
		self.method = method
		self.data = data
		self.headers = headers
		self.service = ChildTransaction.Service(**service)  # type: ChildTransaction.Service

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
		else:
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

				self.parent.threads.append(self.do_ping())  # THREAD:1, loop
				self.parent.threads.append(self.wait_response())  # THREAD:1
				self.parent.threads.append(self.wait_done())  # THREAD:1

	@g_async
	def do_ping(self):
		while not (self.parent.done.ready() or self.fail.ready()):
			debug_SSE.event({"event": "ping_child", "t": datetime.now(), "data": self.id})  # DEBUG ping_child
			try:
				resp = request_lib.get("{}/transactions/{}".format(self.service.url, self.remote_id), headers={
					"X-Transaction": self.key
				}, timeout=self.ping_timeout)  # BLOCK, timeout
			except request_lib.RequestException:
				self.fail.set()  # EMIT(fail)
			else:
				if resp.status_code == 200:
					t = self.ping_timeout - resp.elapsed.total_seconds()
					sleep(t)  # BLOCK, sleep
				else:
					self.fail.set()  # EMIT(fail)

	@g_async
	def wait_done(self):  # DEBUG
		wait([self.done])
		debug_SSE.event({
			"event": "done_child",
			"t": datetime.now(),
			"data": self.id
		})  # DEBUG done_child

	@g_async
	def wait_response(self):  # LISTENER
		debug_SSE.event({
			"event": "prepare_commit_child", "t": datetime.now(),
			"data": self.id
		})  # DEBUG prepare_commit_child
		try:
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
		else:
			self.fail.set()  # EMIT(fail)

	@g_async
	def do_commit(self):
		try:
			# BLOCK, timeout
			resp = request_lib.post("{}/transactions/{}".format(self.service.url, str(self.remote_id)), headers={
				"X-Transaction": self.key
			}, timeout=self.parent.done_timeout)
		except request_lib.RequestException:
			self.fail.set()  # EMIT(fail)
			return False
		if resp.status_code != 200:
			self.fail.set()  # EMIT(fail)
			return False
		debug_SSE.event({
			"event": "commit_child",
			"t": datetime.now(),
			"data": self.id
		})  # DEBUG commit_child
		self.commit.set()
		return True

	@g_async
	def do_rollback(self):
		self.fail.set()
		try:
			# BLOCK, timeout
			resp = request_lib.delete("{}/transactions/{}".format(self.service.url, str(self.remote_id)), headers={
				"X-Transaction": self.key
			}, timeout=self.parent.done_timeout)
		except request_lib.RequestException:
			pass # auto rollback by timeout
		debug_SSE.event({
			"event": "rollback_child",
			"t": datetime.now(),
			"data": self.id
		})  # DEBUG rollback_child

	@g_async
	def send_finish(self):
		resp = request_lib.put("{}/transactions/{}".format(self.service.url, str(self.remote_id)), headers={
			"X-Transaction": self.key
		}, timeout=self.parent.done_timeout)

	# TODO: Check response?
