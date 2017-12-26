import time
from datetime import datetime
from hashlib import sha256
from random import randint
from sqlite3 import Connection
from typing import Callable, Union, List, Iterable

import requests
from bson import ObjectId
from gevent import Greenlet, wait, sleep
from gevent.event import Event

from tools import debug_SSE
from tools.gevent import g_async
from tools.transactions import ATransaction
from . import SqlResult, SqlChain

# def fn(self, *results) -> JSONSerializable
ResultProcessorType = Callable[['SqlTransaction', Iterable[SqlResult], ], Union[str, int, float, dict, list, tuple]]
Seconds = float


class SqlTransaction(ATransaction):
    def __init__(self, connection: Connection, result_processor: ResultProcessorType):
        super().__init__(ObjectId())
        self.connection = connection
        self.result_processor = result_processor

        self.chains: List[SqlChain] = []
        self.result_containers: List[SqlChain] = []

    @g_async
    def execute(self):
        for ch in self.chains:
            ch.execute()
        wait(self.result_containers)
        self.ready_commit.set()

    def add(self, chain: SqlChain, result_container: SqlChain = None):
        """

        :param chain:
        :param result_container: The end of chain that contains the result passed to result_processor
        """
        self.chains.append(chain)
        self.result_containers.append(result_container or chain)

    def get_result(self):  # BLOCK
        return self.result_processor(self, *(container.get() for container in self.result_containers))

    @g_async
    def do_commit(self):
        self.connection.commit()
        self.commit.set()  # EMIT(commit)

    @g_async
    def do_rollback(self):
        self.connection.rollback()
        self.fail.set()  # EMIT(fail)


class RestTransaction(SqlTransaction):
    def __init__(self, connection: Connection, result_processor: ResultProcessorType, callback_url: str,
                 ping_timeout: Seconds, local_timeout: Seconds):
        super(RestTransaction, self).__init__(connection, result_processor)
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

        self._ping = Event()
        self.ping_timeout_thread_obj = None  # type: Greenlet

    @g_async
    def _spawn(self):
        self.ping_timeout_thread_obj = self.ping_timeout_thread()  # THREAD:1, loop

    @g_async
    def ping_timeout_thread(self):
        while not (self.done.ready() or self.fail.ready()):
            debug_SSE.event({"event": "wait_ping", "t": datetime.now(), "data": None})  # DEBUG wait_ping
            w = wait((self._ping, self.done, self.fail),
                     count=1, timeout=self.ping_timeout * 2)  # BLOCK, ping_timeout * 2
            if not len(w):
                debug_SSE.event({"event": "fail", "t": datetime.now(), "data": "ping timeout"})  # DEBUG ping timeout
                super(RestTransaction, self).do_rollback()
                break

            if self._ping.ready():
                debug_SSE.event({"event": "ping", "t": datetime.now(), "data": None})  # DEBUG ping
                self._ping.clear()  # EMIT(-ping)
                sleep()

    def ping(self) -> bool:
        if not (self.fail.ready() or self.done.ready()):
            self._ping.set()  # EMIT(ping)
            return True
        return False

    @g_async
    def do_commit(self):
        if not self.fail.ready():
            if self.ready_commit.ready() and self.result.ready():
                super(RestTransaction, self).do_commit()
                debug_SSE.event({"event": "commit", "t": datetime.now(), "data": None})  # DEBUG commit

                data = self.get_result()
                rp = requests.put(self.callback_url, headers={"Connection": "close"}, json=data)
                debug_SSE.event({"event": "done", "t": datetime.now(), "data": None})  # DEBUG done

    @g_async
    def do_rollback(self):
        super(RestTransaction, self).do_rollback()
        debug_SSE.event({"event": "rollback", "t": datetime.now(), "data": None})  # DEBUG rollback
