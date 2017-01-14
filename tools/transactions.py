from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import List

from gevent import Greenlet
from gevent import event

import tools
from tools.gevent_ import g_async


class EStatus(Enum):
	IN_PROGRESS = 1
	READY_COMMIT = 2
	FAIL = 3
	# TIMEOUT = 4
	COMMITTED = 5


tools.register_type(EStatus, (
	lambda s: str(s).split(".")[1],
	lambda s: EStatus[s]
))


class ATransaction(metaclass=ABCMeta):
	@abstractmethod
	def __init__(self, _id):
		self.id = _id
		self.threads = []  # type: List[Greenlet]
		self.ready_commit = event.Event()
		self.commit = event.Event()
		self.fail = event.Event()
		self.done = event.Event()
		self.response = event.AsyncResult()
		self.main_thread = None  # type: Greenlet

	@property
	def _status(self):
		return self.ready_commit.ready(), self.commit.ready(), self.fail.ready()

	@property
	def status(self):
		cr, c, f = self._status
		if f:
			return EStatus.FAIL
		if c:
			return EStatus.COMMITTED
		if cr:
			return EStatus.READY_COMMIT
		return EStatus.IN_PROGRESS

	def run(self):
		self.main_thread = self._spawn()
		return self.main_thread

	@g_async
	def _spawn(self):
		pass

	def __hash__(self):
		return hash(self.id)
