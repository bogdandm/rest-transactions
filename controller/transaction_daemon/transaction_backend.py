import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import requests as request_lib
from bson import ObjectId
from gevent import Greenlet
from gevent import joinall
from gevent import sleep
from gevent import wait

from tools import debug_SSE, MultiDict, Singleton
from tools import transform_json_types
from tools.gevent_ import g_async, Wait
from tools.transactions import ATransaction

_path = (Path(__file__) / "..").absolute().resolve()


def dict_factory(cursor, row):
	d = {}
	for idx, col in enumerate(cursor.description):
		d[col[0]] = row[idx]
	return d


class TransactionManager(metaclass=Singleton):
	instance = None  # type: TransactionManager
	def_db = ":memory:"

	def __init__(self, db=None):
		TransactionManager.instance = self
		self._transactions = {}  # type: Dict[ObjectId, Transaction]
		self.db = sqlite3.connect(db if db else self.def_db)
		with open(str(_path / "sql.json")) as f:
			self.queries = json.load(f)
		self.init_db()

	def init_db(self):
		self.db.row_factory = dict_factory
		cur = self.db.cursor()
		cur.executescript(self.queries["init"])
		self.db.commit()

	def create(self, data):
		tr = Transaction(data)
		self._transactions[tr.id] = tr

		cur = self.db.cursor()
		cur.execute(self.queries["create"], (str(tr.id),))
		self.db.commit()
		cur.close()

		tr.run()
		return tr

	def __getitem__(self, _id: ObjectId):
		if _id in self._transactions:
			return self._transactions[_id]
		else:
			cur = self.db.cursor()
			cur.execute(self.queries["get"], (str(_id),))
			tr = cur.fetchone()
			cur.close()
			return tr

	def finish(self, tr: 'Transaction'):
		cur = self.db.cursor()
		cur.execute(
			self.queries["fail" if tr.fail.ready() else "complete"],
			(json.dumps(tr.status), str(tr.id))
		)
		self.db.commit()
		cur.close()

		del self._transactions[tr.id]


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
			"global": super().status.name,
			**{ch.id: ch.status.name for ch in self.childes.values()}
		}

	def __repr__(self):
		return "Transaction#{}: {}".format(self.id, super().status)

	@g_async
	def _spawn(self):
		self.global_timeout_thread = self.wait_fail()

		# Phase 1

		# self.threads += [ch.run() for ch in self.childes.values()]  # THREAD:N, blocked
		for ch in self.childes.values():
			self.threads.add(ch.run())
		wait([ch.ready_commit for ch in self.childes.values()])  # BLOCK
		if not self.fail.ready():
			self.ready_commit.set()

		# Phase 2

		if self.ready_commit.ready():
			debug_SSE.event({"event": "ready_commit", "t": datetime.now()})  # DEBUG ready_commit
			self.commit.set()
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
					  then=on_child_fail, parent=self)

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
		self.threads.kill()

		for w in Wait.connections[self]:
			w.kill()
		del Wait.connections[self]
		TransactionManager.instance.finish(self)


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
			if not resp.ok:
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

				self.parent.threads.add(self.do_ping())  # THREAD:1, loop
				self.parent.threads.add(self.wait_response())  # THREAD:1
				self.parent.threads.add(self.wait_done())  # THREAD:1

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
				if resp.ok:
					sleep(self.ping_timeout - resp.elapsed.total_seconds() - 0.1)  # BLOCK, sleep
				else:
					self.fail.set()  # EMIT(fail)

	@g_async
	def wait_done(self):  # DEBUG # LISTENER
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
		if not resp.ok:
			self.fail.set()  # EMIT(fail)
			return

		wait((self.response, self.fail), count=1, timeout=self.service.timeout)  # BLOCK, timeout
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
		if not resp.ok:
			self.fail.set()  # EMIT(fail)
			return False
		debug_SSE.event({
			"event": "commit_child",
			"t": datetime.now(),
			"data": self.id
		})  # DEBUG commit_child
		self.commit.set()

	@g_async
	def do_rollback(self):
		self.fail.set()
		try:
			# BLOCK, timeout
			resp = request_lib.delete("{}/transactions/{}".format(self.service.url, str(self.remote_id)), headers={
				"X-Transaction": self.key
			}, timeout=self.parent.done_timeout)
		except request_lib.RequestException:
			pass  # auto rollback by timeout
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
