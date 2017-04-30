import http.client

import gevent
import requests
import urllib3

from tools import timeit
from tools.gevent_ import g_async

N = 100
M = 100
domen="jsonplaceholder.typicode.com"
url="http://jsonplaceholder.typicode.com/posts/1/comments"
# domen = "ghibliapi.herokuapp.com"
# url = "http://ghibliapi.herokuapp.com/films/58611129-2dbc-4a81-a72f-77ddfc1b1b49"


@timeit
def do1():
	print("http.client")

	@g_async
	def f():
		conn = http.client.HTTPConnection(domen, 80)
		for i in range(N):
			if i % (N // 10) == 0: print(f"{i/N:.0%}")
			conn.request("GET", url)
			trash = conn.getresponse()
			trash.read()

	gevent.wait([f() for _ in range(M)])


@timeit
def do2():
	print("urllib3")
	conn = urllib3.HTTPConnectionPool(domen, maxsize=M)

	@g_async
	def f():
		for i in range(N):
			if i % (N // 10) == 0: print(f"{i/N:.0%}")
			rp: urllib3.HTTPResponse = conn.request("GET", url)
			trash = rp.data

	gevent.wait([f() for _ in range(M)])


@timeit
def do3():
	print("requests")
	conn = requests.Session()

	@g_async
	def f():
		for i in range(N):
			if i % (N // 10) == 0: print(f"{i/N:.0%}")
			rp = conn.request("GET", url)
			trash = rp.text

	gevent.wait([f() for _ in range(M)])


@timeit
def do4():
	print("requests w/o Sessions")

	@g_async
	def f():
		for i in range(N):
			if i % (N // 10) == 0: print(f"{i/N:.0%}")
			rp = requests.request("GET", url)
			trash = rp.text

	gevent.wait([f() for _ in range(M)])


if __name__ == '__main__':
	_, time1 = do1()
	_, time2 = do2()
	_, time3 = do3()
	# _, time4 = do4()
	print(time1, time2, time3)