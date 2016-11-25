import gevent
import gevent.monkey

gevent.monkey.patch_all()


def g_async(f):
	"""
	Wrap function/method to gevent.spawn and return Greenlet object
	:param f:
	:return:
	"""

	def wrapper(*args) -> gevent.Greenlet:
		return gevent.spawn(f, *args)

	return wrapper
