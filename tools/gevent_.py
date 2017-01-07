import sys
from typing import Callable

import gevent
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
