import json
import pyodbc
from datetime import datetime
from typing import Callable

from bson import ObjectId
from gevent.pywsgi import WSGIServer

from tools import debug_SSE, dict_factory
from tools.flask.decorators import validate, json as json_decorator
from . import CONNECTIONS
from .app import TransactionApp


# dict_factory
class App(TransactionApp):
    def __init__(self, root_path, app_root, connection_factory: Callable[[], pyodbc.Connection], debug=True):
        super().__init__(root_path, app_root, connection_factory, debug=debug)

        @self.route("/<any_resource>", methods=["POST"])
        @validate()
        @json_decorator()
        @self.transaction_supported()
        def any_route(any_resource, data, connection: pyodbc.Connection):
            debug_SSE.event({"event": "touch", "t": datetime.now(), "data": any_resource})  # DEBUG touch
            cursor: pyodbc.Cursor = connection.cursor()
            _id = str(ObjectId())
            cursor.execute("INSERT INTO test(id, ch, json_data) VALUES (?, ?, ?)",
                           (_id, any_resource, json.dumps(data)))
            cursor_read: pyodbc.Cursor = connection.cursor()
            cursor_read.execute("SELECT * FROM test WHERE id=?;", (_id,))
            return {"data": dict_factory(cursor_read, cursor_read.fetchone())}


def main(args=None):
    import argparse

    parser = argparse.ArgumentParser(description='Transaction API REST Service')
    parser.add_argument("-n", "--number", default=0, type=int)
    parser.add_argument("-d", "--debug", default=False, action="store_true")
    parser.add_argument("--no_log", default=False, action="store_true")
    parser.add_argument("--no_sse", default=False, action="store_true")
    parser.add_argument("-P", "--path", default=".", type=str)

    args, _ = parser.parse_known_args(args if args else None)

    if not args.no_sse:
        debug_SSE.spawn(("localhost", 9010 + args.number))
    http_server = WSGIServer(
        ('localhost', 5010 + args.number),
        App(
            args.path,
            "/api",
            connection_factory=lambda: pyodbc.connect(CONNECTIONS.MYSQL("test")),
            debug=args.debug),
        log=None if args.no_log else 'default'
    )
    http_server.serve_forever()


if __name__ == '__main__':
    main()
