import json
from datetime import datetime
from typing import Tuple

import gevent
from flask import Blueprint, Flask, Response
from gevent.pywsgi import WSGIServer
from gevent.queue import Queue

from tools import transform_json_types
from tools.flask_.decorators import crossdomain
from tools.gevent_ import g_async


# TODO: docs
class ServerSentEvent(object):
	def __init__(self, data):
		self.data = data
		self.event = None
		self.id = None
		self.desc_map = {
			self.data: "data",
			self.event: "event",
			self.id: "id"
		}

	def encode(self):
		if not self.data:
			return ""
		lines = ["%s: %s" % (v, k) for k, v in self.desc_map.items() if k]
		return "%s\n\n" % "\n".join(lines)


blueprint = Blueprint("debug_SSE", __name__)
_standalone = Flask(__name__)
_queue = Queue()


@g_async
def _ping():
	while True:
		_queue.put("PING")
		gevent.sleep(1)


def _init():
	global blueprint, _standalone

	@blueprint.route("/debug_sse")
	@crossdomain(origin='*')
	def sse():
		def gen():
			global _queue
			yield ServerSentEvent('INIT').encode()

			for result in _queue:
				if isinstance(result, dict):
					result = json.dumps(transform_json_types(result))
				ev = ServerSentEvent(str(result))
				yield ev.encode()
			print("Connection close")

		def onclose():
			stream.close()

		stream = gen()
		resp = Response(stream, mimetype="text/event-stream")
		resp.call_on_close(onclose)
		return resp

	_standalone.register_blueprint(blueprint)


_init()
del _init


@g_async
def spawn(host: Tuple[str, int]):
	global _standalone

	server = WSGIServer(host, _standalone, log=None, error_log=None)
	_ping()
	server.serve_forever()


@g_async
def event(a):
	_queue.put(a)


if __name__ == '__main__':
	port = int(input("port: "))
	th = spawn(("localhost", port))
	s = "init"
	while s:
		s = input("> ")
		_queue.put({"event": "msg", "t": datetime.now(), "data": s})
	print("exit")
