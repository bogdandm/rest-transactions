import logging
from typing import Dict, Any

from gevent.wsgi import WSGIServer
from werkzeug.exceptions import NotFound, BadRequest

from tools.flask import EmptyApp
from tools.flask.decorators import validate, json
from tools.socket.tcp_client import TcpClientThreading


class ControllerRestService(EmptyApp):
    VERSION = "alpha"

    def __init__(self, root_path, app_root="/api/%s" % VERSION):
        super().__init__(root_path, app_root)
        try:
            self.client = TcpClientThreading(("localhost", 5600))
        except ConnectionError as e:
            logging.error(("localhost", 5600, e))
            exit()
        self.register_crossdomain("/transactions", "/transactions/<trid>")

        @self.route("/ping", methods=["GET"])
        @json()
        def ping():
            return "Pong"

        @self.route("/transactions", methods=["POST"])
        @validate(self.schemas["transaction"])
        @json(id_field="ID", hide_id=False)
        def transaction_create(data: Dict[str, Any]):
            header, js = self.client.call("open_transaction", data).values
            if header != "200" and header != 200:
                raise Exception(header, js)
            else:
                return {**js, "OK": True}

        @self.route("/transactions/<trid>", methods=["GET"])
        @json()
        def transaction_get(trid):
            header, js = self.client.call("get_transaction", {"id": trid}).values
            if header == "404":
                raise NotFound()
            elif header != "200":
                raise Exception(header, js)
            else:
                return js

        @self.route("/transactions/<trid>", methods=["PUT"])
        @validate(self.schemas["service_status_callback"])
        @json()
        def transaction_put_response(trid, data: Dict[str, Any]):
            if "response" in data:
                header, js = self.client.call("set_result", {"id": trid, **data}).values
            elif "done" in data:
                header, js = self.client.call("set_done", {"id": trid, **data}).values
            else:
                raise BadRequest()
            if header == "200":
                return js
            elif header == "404":
                raise NotFound(response=trid)
            else:
                raise Exception(header, js)

            # @self.route("/transaction/<trid>", methods=["DELETE"])
            # @json()
            # def r_transaction_get(trid):
            # 	pass
            #
            # @self.route("/transaction/<trid>", methods=["POST"])
            # @validate(self.schemas["service_status_callback.schema"])
            # @json()
            # def r_transaction_get(data, trid):
            # 	pass


def main(args=None):
    import argparse

    parser = argparse.ArgumentParser(description='Controller API REST Service')
    parser.add_argument("--no_log", default=False, action="store_true")
    parser.add_argument("-P", "--path", default=".", type=str)
    parser.add_argument("-p", "--port", default=5000, type=int)

    if args:
        args, _ = parser.parse_known_args(args)
    else:
        args, _ = parser.parse_known_args()

    http_server = WSGIServer(('', args.port), ControllerRestService(args.path), log=None if args.no_log else 'default')
    http_server.serve_forever()


if __name__ == '__main__':
    main()
