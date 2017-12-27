from datetime import datetime
from typing import Any, Callable, Optional
from typing import Dict

from flask import request
from werkzeug.exceptions import NotFound

from sql_transactions.transactions import RestTransaction
from tools import debug_SSE, MultiDict
from tools.flask import EmptyApp
from tools.flask.decorators import validate, json


class TransactionApp(EmptyApp):
    def __init__(self, root_path, app_root, debug=True):
        super().__init__(root_path, app_root, extended_errors=debug, debug=debug)
        self.transactions: Dict[Any, RestTransaction] = MultiDict()

        @self.route("/transactions", methods=["POST"])
        @validate(self.schemas["transaction_post"])
        @json(id_field="_id")
        def transaction_post(data):
            pass

        @self.route("/transactions/<trid>", methods=["GET"])
        @json()
        # PING
        def transaction_id_get(trid):
            tr = self.transactions.get(trid)
            key = request.headers["X-Transaction"]
            if tr is None or tr.key != key:
                raise NotFound
            return {"alive": tr.ping()}

        @self.route("/transactions/<trid>", methods=["POST"])
        @json()
        # COMMIT
        def transaction_id_post(trid):
            tr = self.transactions.get(trid)
            key = request.headers["X-Transaction"]
            if tr is None or tr.key != key:
                raise NotFound
            tr.do_commit()
            return ""

        @self.route("/transactions/<trid>", methods=["PUT"])
        @json()
        # FINISH
        def transaction_id_put(trid):
            tr = self.transactions.get(trid)
            key = request.headers["X-Transaction"]
            if tr is None or tr.key != key:
                raise NotFound
            tr.done.set()
            debug_SSE.event({"event": "finish", "t": datetime.now(), "data": None})  # DEBUG finish
            return ""

        @self.route("/transactions/<trid>", methods=["DELETE"])
        @json()
        # ROLLBACK
        def transaction_id_delete(trid):
            tr = self.transactions.get(trid)
            key = request.headers["X-Transaction"]
            if tr is None or tr.key != key:
                raise NotFound
            tr.do_rollback()
            return {"OK": tr.fail.ready()}

    @property
    def transaction(self) -> Optional[RestTransaction]:
        return self.transactions.get(request.headers.get("X-Transaction", None), None)

    def transaction_supported(self, fn: Callable):
        def wrapper(self, *args, **kwargs):
            transaction = self.transaction
            if not transaction:
                return fn(self, *args, **kwargs)




        wrapper.__name__ = fn.__name__
        return wrapper
