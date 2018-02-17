import pyodbc
import time
from datetime import datetime
from functools import partial
from hashlib import sha256
from random import randint
from typing import List, Set, Callable, Any, Dict, Iterable, Union, Tuple

import requests
from bson import ObjectId
from gevent import Greenlet, wait, sleep, spawn
from gevent.event import AsyncResult
from gevent.event import Event

from tools import debug_SSE, Seconds, dict_factory
from tools.gevent import g_async
from tools.transactions import ATransaction

# def fn(self, *results) -> JSONSerializable
SqlResult = Dict[str, Any]


class SqlChain(AsyncResult):
    """
    Connect SQL execute calls into chain object and call them one in sequence
    """
    VarsFnType = Callable[
        [Tuple[SqlResult, ...]],
        Union[Iterable, Dict[str, Any]]
    ]

    def __init__(self, sql: str, vars: List = None, vars_fn: VarsFnType = None,
                 cursor: pyodbc.Cursor = None, parent: 'SqlChain' = None):
        """

        :param sql: SQL code
        :param vars: Arguments for sql
        :param vars_fn: Arguments getter: def fn(self, *results) -> JSONSerializable
        :param cursor: cursor to execute. Required for 'parent' object
        :param parent: parent object. Used in SqlChain::chain call
        """
        super().__init__()
        self.sql = sql
        self.vars = vars
        self.vars_fn = vars_fn
        self.cursor = cursor or parent.cursor

        self.child: Set[SqlChain] = set()
        self.root = parent.root if parent else self
        self.nodes = {self} if self.is_root else None

    @property
    def is_root(self):
        return self.root is self

    @g_async
    def execute(self, parent_result: Iterable = ()):
        """Execute stored SQL"""
        args = self.vars or (self.vars_fn(*parent_result) if self.vars_fn else ())
        try:
            self.cursor.execute(self.sql, args)
            try:
                result: Iterable[SqlResult] = [dict_factory(self.cursor, row) for row in self.cursor]
            except pyodbc.ProgrammingError:
                result = []
            self.set(result)
            for ch in self.child:
                ch.execute(result)  # THREAD:1
        except pyodbc.Error as e:
            result = e
            for node in self.root.nodes:
                node.set(e)
            self.set(e)
        return result

    def chain(self, sql: str, *args, vars_fn: VarsFnType = None, **kwargs) -> 'SqlChain':
        """Create child object. Arguments same as __init__"""
        new_node = self.__class__(sql=sql, parent=self, *args, vars_fn=vars_fn, **kwargs)
        self.child.add(new_node)
        self.root.nodes.add(new_node)
        return new_node

    def close(self):
        """Close all cursors in chain"""
        self.cursor.close()
        for ch in self.nodes:
            try:
                ch.cursor.close()
            except pyodbc.ProgrammingError:
                continue


class RestTransactionMixin(ATransaction):
    """Wrap ATransaction class to create RestTransaction class"""

    def __init__(self, _id, callback_url: str, ping_timeout: Seconds, local_timeout: Seconds):
        """

        :param _id: transaction_id (local)
        :param callback_url: url to send results of commit
        :param ping_timeout: timeout (seconds) of checking service status
        :param local_timeout: timeout (seconds) of local transaction
        """
        ATransaction.__init__(self, _id)
        self.callback_url = callback_url
        self.ping_timeout = ping_timeout
        self.local_timeout = local_timeout

        self.key = sha256(bytes(
            str(self.id) + str(int(time.time() * 10 ** 6) ^ randint(0, 2 ** 20)),
            encoding="utf-8"
        )).hexdigest()

        debug_SSE.event({"event": "init", "t": datetime.now(), "data": {
            "callback_url": self.callback_url,
            "local_timeout": self.local_timeout * 1000,
            "ping_timeout": self.ping_timeout * 1000,
            "key": self.key,
            "_id": self.id
        }})  # DEBUG init

        self._ping = Event()  # store ping event
        self.ping_timeout_thread_obj: Greenlet = None

    @g_async
    def _spawn(self):
        self.ping_timeout_thread_obj = self.ping_timeout_thread()  # THREAD:1, loop
        self.ready_commit_thread_obj = self.ready_commit_handler() # THREAD:1

    @g_async
    def ping_timeout_thread(self):
        while not (self.done.ready() or self.fail.ready()):
            debug_SSE.event({"event": "wait_ping", "t": datetime.now(), "data": None})  # DEBUG wait_ping
            w = wait((self._ping, self.done, self.fail),
                     count=1, timeout=self.ping_timeout * 2)  # BLOCK, ping_timeout * 2
            if not len(w):
                debug_SSE.event({"event": "fail", "t": datetime.now(), "data": "ping timeout"})  # DEBUG ping timeout
                super().do_rollback()
                break

            if self._ping.ready():
                debug_SSE.event({"event": "ping", "t": datetime.now(), "data": None})  # DEBUG ping
                self._ping.clear()  # EMIT(-ping)
                sleep()

    def ping(self) -> bool:
        """Ping request handler"""
        if not (self.fail.ready() or self.done.ready()):
            self._ping.set()  # EMIT(ping)
            return True
        return False

    @g_async
    def ready_commit_handler(self):
        wait((self.ready_commit,), self.local_timeout) # BLOCK, local_timeout
        if not self.fail.ready():
            debug_SSE.event({"event": "ready_commit", "t": datetime.now(), "data": None})  # DEBUG ready_commit
            data = {
                "key": self.key,
                "response": {
                    "data": self.result.get()
                }
            }
            rp = requests.put(self.callback_url, headers={"Connection": "close"}, json=data, timeout=5)

    @g_async
    def do_commit(self):
        if not self.fail.ready() and self.ready_commit.ready() and self.result.ready():
            super().do_commit()
            debug_SSE.event({"event": "commit", "t": datetime.now(), "data": None})  # DEBUG commit

            data = {
                "key": self.key,
                "done": True
            }
            rp = requests.put(self.callback_url, headers={"Connection": "close"}, json=data)
            debug_SSE.event({"event": "done", "t": datetime.now(), "data": None})  # DEBUG done

    @g_async
    def do_rollback(self):
        super().do_rollback()
        debug_SSE.event({"event": "rollback", "t": datetime.now(), "data": None})  # DEBUG rollback


class SqlTransaction(ATransaction):
    """Create transaction of SqlChain object[s]"""
    ResultProcessorType = Callable[
        ['SqlTransaction', Tuple[Iterable[SqlResult], ...]],
        Union[str, int, float, dict, list, tuple]
    ]

    def __init__(self, connection: pyodbc.Connection, result_processor: ResultProcessorType):
        """

        :param connection:
        :param result_processor: Function to convert SQL results to any python objects
            def f(sql_transaction, *sql_results)
        """
        super().__init__(ObjectId())
        self.connection = connection
        self.result_processor = result_processor

        self.chains: List[SqlChain] = []
        self.result_containers: List[SqlChain] = []

    @g_async
    def _spawn(self):
        for ch in self.chains:
            ch.execute()
        wait(self.result_containers)
        self.ready_commit.set()

    def add(self, chain: SqlChain, result_container: SqlChain = None):
        """

        :param chain:
        :param result_container: The end of chain that contains the result which will be sent to result_processor
        """
        self.chains.append(chain)
        self.result_containers.append(result_container or chain)

    def get_result(self):  # BLOCK
        return self.result_processor(self, *(container.get() for container in self.result_containers))

    @g_async
    def do_commit(self):
        self.connection.commit()
        for ch in self.chains:
            ch.close()
        self.commit.set()  # EMIT(commit)

    @g_async
    def do_rollback(self):
        self.connection.rollback()
        for ch in self.chains:
            ch.close()
        self.fail.set()  # EMIT(fail)


class RestSqlTransaction(RestTransactionMixin, SqlTransaction):
    def __init__(self, connection: pyodbc.Connection, result_processor: SqlTransaction.ResultProcessorType,
                 callback_url: str,
                 ping_timeout: Seconds, local_timeout: Seconds):
        RestTransactionMixin.__init__(
            self,
            _id=None,
            callback_url=callback_url,
            ping_timeout=ping_timeout,
            local_timeout=local_timeout
        )
        SqlTransaction.__init__(self, connection, result_processor)

    def _spawn(self):
        RestTransactionMixin._spawn(self)
        return SqlTransaction._spawn(self)


class RouteWrapperTransaction(ATransaction):
    """Wrap Flask App route into transaction"""

    def __init__(self, connection: pyodbc.Connection):
        ATransaction.__init__(self, ObjectId())
        self.connection = connection

    def wrap(self, route: Callable, *args, **kwargs):
        self.route = partial(route, *args, connection=self.connection, **kwargs)

    @g_async
    def _spawn(self):
        self.result.set(spawn(self.route).get())
        self.ready_commit.set()

    @g_async
    def do_commit(self):
        self.connection.commit()
        self.commit.set()  # EMIT(commit)

    @g_async
    def do_rollback(self):
        self.connection.rollback()
        self.fail.set()  # EMIT(fail)


class RestRouteWrapperTransaction(RestTransactionMixin, RouteWrapperTransaction):
    def __init__(self, connection: pyodbc.Connection, callback_url: str, ping_timeout: Seconds, local_timeout: Seconds):
        RestTransactionMixin.__init__(
            self,
            _id=None,
            callback_url=callback_url,
            ping_timeout=ping_timeout,
            local_timeout=local_timeout
        )
        RouteWrapperTransaction.__init__(self, connection)

    def _spawn(self):
        RestTransactionMixin._spawn(self)
        return RouteWrapperTransaction._spawn(self)
