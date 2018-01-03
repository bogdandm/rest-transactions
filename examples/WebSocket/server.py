from ws4py.websocket import WebSocket


class ExampleServer(WebSocket):
    def received_message(self, message):
        print(message)
        super().received_message(message)


if __name__ == '__main__':
    from gevent import monkey

    monkey.patch_all()
    from ws4py.server.geventserver import WSGIServer
    from ws4py.server.wsgiutils import WebSocketWSGIApplication

    server = WSGIServer(('localhost', 9000), WebSocketWSGIApplication(handler_cls=ExampleServer))
    server.serve_forever()
