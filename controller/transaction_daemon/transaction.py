from enum import Enum

import requests as request_lib
from bson import ObjectId
from gevent import killall
from gevent import sleep
from gevent import wait
from gevent.event import AsyncResult, Event

from tools.gevent_ import g_async


# TODO: then statement

class EStatus(Enum):
	IN_PROGRESS = 1
	WAIT = 2
	FAIL = 3
	TIMEOUT = 4
	FINISH = 5


class Transaction:
	self_url = ""

	@classmethod
	def set_self_url(cls, url: str):
		cls.self_url = url

	def __init__(self, data: dict):
		"""
		>>> data_template = {
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
		self.id = ObjectId()
		self.timeout = data["timeout"] * 1000
		self.childes = {tr["_id"]: ChildTransaction(self, **tr) for tr in data["actions"].values()}

		self.finish = Event()
		self.fail = Event()
		self.threads = []

	@property
	def status(self):
		# (finish.ready, fail.ready) => status
		m = {
			(False, False): EStatus.IN_PROGRESS,
			(False, True): EStatus.FAIL,
			(True, False): EStatus.FINISH,
			(True, True): EStatus.FAIL
		}
		f = lambda tr: (tr.finish.ready(), tr.fail.ready())
		return {
			**{ch.service.name: m[f(ch)] for ch in self.childes},
			"global": m[f(self)]
		}

	@g_async
	def spawn(self):
		self.threads += [tr.spawn() for tr in self.childes]  # THREAD:N, blocked
		self.wait_fail()
		self.wait_finish()
		wait((self.finish, self.fail), count=1)  # BLOCK # LISTENER
		killall(self.threads)  # THREAD:?, kill

	@g_async
	def wait_finish(self): # LISTENER
		wait(map(
			lambda ch: ch.finish,
			self.childes
		))  # BLOCK
		self.finish.set() # EMIT(finish)

	@g_async
	def wait_fail(self): # LISTENER
		wait(map(
			lambda ch: ch.fail,
			self.childes
		), count=1, timeout=self.timeout)  # BLOCK, timeout
		self.fail.set() # EMIT(fail)


class ChildTransaction:
	class Service:
		def __init__(self, name, url, timeout):
			self.name = name
			self.url = url
			self.timeout = timeout * 1000

	def __init__(self, parent: 'Transaction', _id: str, url: str, method: str, data: dict, headers: dict,
				 service: dict, **kwargs):
		self.parent = parent

		self._id = _id
		self.url = url
		self.method = method
		self.data = data
		self.headers = headers
		self.service = ChildTransaction.Service(**service)

		self.remote_id = None
		self.key = None
		self.ping_timeout = -1

		self.response = AsyncResult()
		self.fail = Event()
		self.finish = Event()

	def set_resp(self, resp: request_lib.Response):
		if resp.status_code != 200:
			self.fail.set() # EMIT(fail)
		else:
			self.response.set(resp) # EMIT(response)

	@g_async
	def spawn(self):
		try:
			resp = request_lib.post(self.service.url + "/transaction", {
				"timeout": self.parent.timeout * 3 / 4,
				"callback-url": "{}/{}".format(self.parent.self_url, self.parent.id)
			}, timeout=self.parent.timeout / 4)  # BLOCK, timeout
		except:
			self.fail.set() # EMIT(fail)
			return

		if resp.status_code != 200:
			self.fail.set() # EMIT(fail)
		else:
			js = resp.json()
			# TODO: validate
			self.remote_id = js["_id"]
			self.key = js["transaction-key"]
			self.ping_timeout = js["ping_timeout"] * 1000

			self.parent.threads.append(self.ping())  # THREAD:1, loop
			self.parent.threads.append(self.wait_response())  # THREAD:1

	@g_async
	def ping(self):
		while not self.finish.ready() and not self.fail.ready():
			try:
				resp = request_lib.get(self.service.url + "/transaction/" + self.remote_id, headers={
					"X-Transaction": self.key
				}, timeout=self.ping_timeout)  # BLOCK, timeout
				if resp.status_code != 200:
					self.fail.set() # EMIT(fail)
					return
			except:
				self.fail.set() # EMIT(fail)
				return
			sleep(self.ping_timeout)
		# Max timeout sum is 2*ping_timeout

	@g_async
	def wait_response(self): # LISTENER
		wait(self.response, timeout=self.service.timeout)  # BLOCK, timeout
		if self.response.successful():
			if self.response.get().status_code == 200:
				self.finish.set() # EMIT(finish)
				return
		self.fail.set() # EMIT(fail)
