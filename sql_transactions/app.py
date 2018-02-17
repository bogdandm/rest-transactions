import pyodbc
from datetime import datetime
from typing import Any, Callable, Optional
from typing import Dict

from flask import request
from werkzeug.exceptions import NotFound

from sql_transactions.transactions import RestRouteWrapperTransaction
from tools import debug_SSE, MultiDict
from tools.flask import EmptyApp
from tools.flask.decorators import validate, json


class TransactionApp(EmptyApp):
    PING_T_O = 2  # sec

    def __init__(self, root_path, app_root, connection_factory: Callable[[], pyodbc.Connection], debug=True):
        super().__init__(root_path, app_root, extended_errors=debug, debug=debug)
        self.connection_factory = connection_factory
        self.transactions: Dict[Any, RestRouteWrapperTransaction] = MultiDict()

        @self.route("/transactions", methods=["POST"])
        @validate(self.schemas["transaction_post"])
        @json(id_field="_id")
        def transaction_create(data):
            tr = RestRouteWrapperTransaction(
                connection=self.connection_factory(),
                callback_url=data["callback-url"],
                local_timeout=data["timeout"] / 1000,
                ping_timeout=self.PING_T_O
            )
            self.transactions[str(tr.id)] = tr
            self.transactions[tr.key] = tr
            return {
                "_id": str(tr.id),
                "transaction-key": tr.key,
                "ping-timeout": tr.ping_timeout * 1000
            }

        @self.route("/transactions/<trid>", methods=["GET"])
        @json()
        # PING
        def transaction_get(trid):
            tr = self.transactions.get(trid)
            key = request.headers["X-Transaction"]
            if tr is None or tr.key != key:
                raise NotFound
            return {"alive": tr.ping()}

        @self.route("/transactions/<trid>", methods=["POST"])
        @json()
        # COMMIT
        def transaction_commit(trid):
            tr = self.transactions.get(trid)
            key = request.headers["X-Transaction"]
            if tr is None or tr.key != key:
                raise NotFound
            tr.do_commit()
            return ""

        @self.route("/transactions/<trid>", methods=["PUT"])
        @json()
        # FINISH
        def transaction_done(trid):
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
        def transaction_rollback(trid):
            tr = self.transactions.get(trid)
            key = request.headers["X-Transaction"]
            if tr is None or tr.key != key:
                raise NotFound
            tr.do_rollback()
            return {"OK": tr.fail.ready()}

    @property
    def transaction(self) -> Optional[RestRouteWrapperTransaction]:
        return self.transactions.get(request.headers.get("X-Transaction", None), None)

    def _transaction_response(self, transaction: Optional[RestRouteWrapperTransaction]) -> dict:
        return {
            "transaction": {
                "key": transaction.key,
                "status": transaction.status
            }
        } if transaction else {}

    @property
    def transaction_response(self) -> dict:
        return self._transaction_response(self.transaction)

    def transaction_supported(self):
        def decorator(fn: Callable):
            def wrapper(*args, **kwargs):
                transaction = self.transaction
                if not transaction:
                    return fn(self, *args, connection=self.connection_factory(), **kwargs)
                else:
                    transaction.wrap(fn, *args, **kwargs)
                    transaction.run()
                    return self._transaction_response(transaction)

            wrapper.__name__ = fn.__name__
            return wrapper

        return decorator
