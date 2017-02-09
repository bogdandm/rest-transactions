import sys
from collections import defaultdict
from typing import Callable, Dict, List

import gevent
import gevent.event
import gevent.fileobject
import gevent.monkey
import gevent.select

gevent.monkey.patch_all()
sys.stdin = gevent.fileobject.FileObject(sys.stdin)


def g_async(f: Callable) -> Callable[[], gevent.Greenlet]:
	"""
	Decorator. Wrap function/method to gevent.spawn and return Greenlet object
	:param f:
	:return:
	"""

	def wrapper(*args) -> gevent.Greenlet:
		return gevent.spawn(f, *args)

	return wrapper


class Wait:
	"""
	Object which allow to connect wait() and AsyncResult().
	After wait conditions was completed .result will contain wait() return value

	>>> some_event_1 = gevent.event.Event()
	... some_event_2 = gevent.event.Event()
	... w1 = Wait((some_event_1,), timeout=10, then=lambda e: print(e))
	... w2 = Wait((some_event_2,), timeout=5, then=lambda e: print(e))
	... # spawn another threads
	...	gevent.wait((w1.result, w2.result), count=1)
	... w1.kill(), w2.kill()
	"""
	connections = defaultdict(list)  # type: Dict[object, List[Wait]]

	def __init__(self, *args, then=None, parent=None, **kwargs):
		self._args = args
		self._kwargs = kwargs
		self.result = gevent.event.AsyncResult()
		self._thread = self._wait()  # type: gevent.Greenlet
		self._then = then

		if parent:
			Wait.connections[parent].append(self)

	@g_async
	def _wait(self):
		e = gevent.wait(*self._args, **self._kwargs)
		if self._then:
			self._then(e)
		self.result.set(e)

	def kill(self):
		self._thread.kill()
