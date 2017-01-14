import sys
from typing import Callable

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
	def __init__(self, *args, then=None, **kwargs):
		self._args = args
		self._kwargs = kwargs
		self.result = gevent.event.AsyncResult()
		self._thread = self._wait()  # type: gevent.Greenlet
		self._then = then

	@g_async
	def _wait(self):
		e = gevent.wait(*self._args, **self._kwargs)
		if self._then:
			self._then(e)
		self.result.set(e)

	def kill(self):
		self._thread.kill()
