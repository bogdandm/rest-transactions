import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from urllib.parse import urlparse, ParseResult

import urllib3
from bson import ObjectId
from gevent import Greenlet
from gevent import joinall
from gevent import sleep
from gevent import wait

from tools import debug_SSE, Singleton, MultiDict, dict_factory
from tools import transform_json_types
from tools.gevent import g_async, Wait
from tools.transactions import ATransaction

_path = (Path(__file__) / "..").absolute().resolve()


class HTTPConnectionPoolWithLock(urllib3.HTTPConnectionPool):
    def __init__(self, host, **conn_kw):
        super().__init__(host, **conn_kw)
        self.lock = 0

    def acquire(self):
        self.lock += 1

    def release(self):
        if self.lock:
            self.lock -= 1


class TransactionManager(metaclass=Singleton):
    instance: 'TransactionManager' = None
    def_db = ":memory:"

    def __init__(self, db=None):
        TransactionManager.instance = self
        self._transactions: Dict[ObjectId, Transaction] = {}
        self._connections: Dict[str, HTTPConnectionPoolWithLock] = {}
        self.db = sqlite3.connect(db if db else self.def_db)
        with open(str(_path / "sql.json")) as f:
            self.queries = json.load(f)
        self.init_db()

    def init_db(self):
        self.db.row_factory = dict_factory
        cur = self.db.cursor()
        cur.executescript(self.queries["init"])
        self.db.commit()

    def create(self, data):
        tr = Transaction(data)
        self._transactions[tr.id] = tr

        cur = self.db.cursor()
        cur.execute(self.queries["create"], (str(tr.id),))
        self.db.commit()
        cur.close()

        tr.run()
        return tr

    def finish(self, tr: 'Transaction'):
        cur = self.db.cursor()
        cur.execute(
            self.queries["fail" if tr.fail.ready() else "complete"],
            (json.dumps(tr.status), str(tr.id))
        )
        self.db.commit()
        cur.close()

        del self._transactions[tr.id]

    def connect(self, host: str, port: int):
        key = host + ':' + str(port)
        if key not in self._connections:
            conn = self._connections[key] = HTTPConnectionPoolWithLock(
                host, port=port, block=True, maxsize=1000,
                headers={"Content-Type": "application/json"}
            )
        else:
            conn = self._connections[key]
        conn.acquire()
        return conn

    def disconnect(self, host: str, port: int):
        key = host + ':' + str(port)
        conn = self._connections.get(key)
        if conn:
            conn.release()
            if conn.lock == 0:
                conn.close()
                del self._connections[key]

    def __getitem__(self, _id: ObjectId):
        if _id in self._transactions:
            return self._transactions[_id]
        else:
            cur = self.db.cursor()
            cur.execute(self.queries["get"], (str(_id),))
            tr = cur.fetchone()
            cur.close()
            return tr


class Transaction(ATransaction):
    done_timeout = 30  # s
    self_url = "http://localhost:5000/api"

    @classmethod
    def set_self_url(cls, url: str):
        cls.self_url = url

    def __init__(self, data: dict):
        """
        >>> data = {
        ... 	"timeout": "ms",  # Global timeout of whole transaction
        ... 	"actions": [
        ... 		{
        ... 			"_id": "unique str",
        ... 			"service": {
        ... 				"url": "uri",
        ... 				"timeout": "ms"  # local timeout
        ... 			},
        ... 			"url": "uri + GET params",
        ... 			"method": "HTTP method",
        ... 			"data": {},
        ... 			"headers": {},
        ... 			"then": None  #TODO: Support in future versions
        ... 		}
        ... 		# ...
        ... 	]
        ... }

        :param data:
        """
        super().__init__(ObjectId())
        debug_SSE.event({"event": "init", "t": datetime.now(), "data": data})  # DEBUG init
        self.global_timeout = data["timeout"] / 1000
        self.global_timeout_thread: Greenlet = None
        self.childes: Dict[Any, ChildTransaction] = MultiDict(
            {tr["_id"]: ChildTransaction(self, **tr) for tr in data["actions"]}
        )

    @property
    def status(self):
        return {
            "global": super().status.name,
            **{ch.id: {
                "status": ch.status.name,
                "service_response": ch.result.value
            } for ch in self.childes.values()}
        }

    def __repr__(self):
        return "Transaction#{}: {}".format(self.id, super().status)

    @g_async
    def _spawn(self):
        self.global_timeout_thread = self.wait_fail()

        # Phase 1

        # self.threads += [ch.run() for ch in self.childes.values()]  # THREAD:N, blocked
        for ch in self.childes.values():
            self.threads.add(ch.run())
        wait([ch.ready_commit for ch in self.childes.values()])  # BLOCK
        if not self.fail.ready():
            self.ready_commit.set()

        # Phase 2

        if self.ready_commit.ready():
            debug_SSE.event({"event": "ready_commit", "t": datetime.now()})  # DEBUG ready_commit
            self.commit.set()
            debug_SSE.event({"event": "commit", "t": datetime.now()})  # DEBUG commit
            joinall([ch.do_commit() for ch in self.childes.values()])  # BLOCK  # THREAD:N

            # THREAD: 1, blocked
            done = wait(
                [ch.done for ch in self.childes.values()], count=len(self.childes), timeout=self.done_timeout
            )
            if not self.fail.ready() and len(done) == len(self.childes):
                self.done.set()  # EMIT(ready_commit)
                debug_SSE.event({"event": "finish", "t": datetime.now()})  # DEBUG finish
                joinall([ch.send_finish() for ch in self.childes.values()])
            else:
                self.fail.set()
            self.clean()

    @g_async
    def wait_fail(self):
        def on_child_fail(e):
            ch = next(filter(lambda ch: ch.fail.ready(), self.childes.values()), None)
            debug_SSE.event(
                {"event": "fail_child", "t": datetime.now(), "data": ch.id if ch else None})  # DEBUG fail_child
            self.fail.set()  # EMIT(fail)

        w_fail = Wait([ch.fail for ch in self.childes.values()], count=1, timeout=self.global_timeout,
                      then=on_child_fail, parent=self)

        e = wait((self.fail, self.done), count=1, timeout=self.global_timeout)
        if self.done.ready(): return
        self.main_thread.kill()
        self.do_rollback("global timeout" if len(e) == 0 else None)
        self.clean()

    def do_rollback(self, reason=None):
        debug_SSE.event({"event": "fail", "t": datetime.now(), "data": reason})  # DEBUG fail
        joinall([ch.do_rollback() for ch in self.childes.values()])  # BLOCK  # THREAD:N
        debug_SSE.event({"event": "rollback", "t": datetime.now()})  # DEBUG rollback

    @g_async
    def clean(self):
        super(Transaction, self).clean()
        self.global_timeout_thread.kill()
        for ch in self.childes.values():
            url = ch.service.url
            TransactionManager.instance.disconnect(url.hostname, url.port)

        for w in Wait.connections[self]:
            w.kill()
        del Wait.connections[self]
        TransactionManager.instance.finish(self)


class ChildTransaction(ATransaction):
    class Service:
        def __init__(self, url, timeout):
            self.url: ParseResult = urlparse(url[:-1] if url.endswith("/") else url)
            self.session = TransactionManager.instance.connect(self.url.hostname, self.url.port)
            self.timeout = timeout / 1000

        def __repr__(self):
            return f"<{self.url.path}>"

    def __init__(self, parent: 'Transaction', _id: str, url: str, method: str, data: dict, headers: dict, service: dict,
                 **kwargs):
        super().__init__(_id)
        debug_SSE.event({"event": "init_child", "t": datetime.now(), "data": _id})  # DEBUG init_child
        self.parent = parent

        self.url = url
        self.method = method
        self.data = data
        self.headers = headers
        self.service: ChildTransaction.Service = ChildTransaction.Service(**service)

        self.remote_id = None
        self.key = None
        self.ping_timeout = -1

    @g_async
    def _spawn(self):
        try:
            resp: urllib3.HTTPResponse = self.service.session.request(
                "POST", self.service.url.path + "/transactions",
                body=json.dumps({
                    "timeout": self.service.timeout,
                    "callback-url": f"{self.parent.self_url}/{self.parent.id}"
                }),
                timeout=self.service.timeout
            )  # BLOCK, timeout
        except urllib3.exceptions.HTTPError as e:
            self.fail.set()  # EMIT(fail)
        else:
            if resp.status != 200:
                self.fail.set()  # EMIT(fail)
            else:
                js = json.loads(resp.data)
                transform_json_types(js, direction=1)
                # TODO: validate

                debug_SSE.event({
                    "event": "init_child_2", "t": datetime.now(),
                    "data": {"chid": self.id, **js}
                })  # DEBUG init_child_2

                self.remote_id = js["_id"]
                self.key = js["transaction-key"]
                self.parent.childes[self.key] = self
                self.ping_timeout = js["ping-timeout"] / 1000

                self.parent.threads.add(self.do_ping())  # THREAD:1, loop
                self.parent.threads.add(self.wait_response())  # THREAD:1
                self.parent.threads.add(self.wait_done())  # THREAD:1

    @g_async
    def do_ping(self):
        while not (self.parent.done.ready() or self.fail.ready()):
            debug_SSE.event({"event": "ping_child", "t": datetime.now(), "data": self.id})  # DEBUG ping_child
            try:
                start = datetime.now()
                resp: urllib3.HTTPResponse = self.service.session.request(
                    "GET", f"{self.service.url.path}/transactions/{self.remote_id}",
                    headers={
                        "X-Transaction": self.key
                    }, timeout=self.ping_timeout
                )  # BLOCK, timeout
            except urllib3.exceptions.HTTPError:
                self.fail.set()  # EMIT(fail)
            else:
                if resp.status != 200:
                    self.fail.set()  # EMIT(fail)
                else:
                    end = datetime.now()
                    sleep(self.ping_timeout - (end - start).total_seconds() - 0.1)  # BLOCK, sleep

    @g_async
    def wait_done(self):  # DEBUG # LISTENER
        wait([self.done])
        debug_SSE.event({
            "event": "done_child",
            "t": datetime.now(),
            "data": self.id
        })  # DEBUG done_child

    @g_async
    def wait_response(self):  # LISTENER
        debug_SSE.event({
            "event": "prepare_commit_child", "t": datetime.now(),
            "data": self.id
        })  # DEBUG prepare_commit_child
        try:
            resp: urllib3.HTTPResponse = self.service.session.request(
                self.method, self.service.url.path + self.url,
                headers={
                    "X-Transaction": self.key, **self.headers
                },
                body=json.dumps(self.data),
                timeout=self.service.timeout
            )  # BLOCK, timeout
        except urllib3.exceptions.HTTPError:
            self.fail.set()  # EMIT(fail)
            return
        if resp.status != 200:
            self.fail.set()  # EMIT(fail)
            return

        wait((self.result, self.fail), count=1, timeout=self.service.timeout)  # BLOCK, timeout
        if self.result.successful():
            js = self.result.get()
            debug_SSE.event({
                "event": "ready_commit_child", "t": datetime.now(),
                "data": {"chid": self.id, **js}
            })  # DEBUG ready_commit_child
            self.ready_commit.set()  # EMIT(ready_commit)
        else:
            self.fail.set()  # EMIT(fail)

    @g_async
    def do_commit(self):
        try:
            # BLOCK, timeout
            resp: urllib3.HTTPResponse = self.service.session.request(
                "POST", f"{self.service.url.path}/transactions/{self.remote_id}", headers={
                    "X-Transaction": self.key
                },
                timeout=self.parent.done_timeout
            )
        except urllib3.exceptions.HTTPError:
            self.fail.set()  # EMIT(fail)
            return False
        if resp.status != 200:
            self.fail.set()  # EMIT(fail)
            return False
        debug_SSE.event({
            "event": "commit_child",
            "t": datetime.now(),
            "data": self.id
        })  # DEBUG commit_child
        self.commit.set()

    @g_async
    def do_rollback(self):
        self.fail.set()
        try:
            # BLOCK, timeout
            resp: urllib3.HTTPResponse = self.service.session.request(
                "DELETE", f"{self.service.url.path}/transactions/{self.remote_id}",
                headers={
                    "X-Transaction": self.key
                },
                timeout=self.parent.done_timeout
            )
        except urllib3.exceptions.HTTPError:
            pass  # auto rollback by timeout
        debug_SSE.event({
            "event": "rollback_child",
            "t": datetime.now(),
            "data": self.id
        })  # DEBUG rollback_child

    @g_async
    def send_finish(self):
        resp: urllib3.HTTPResponse = self.service.session.request(
            "PUT", f"{self.service.url.path}/transactions/{self.remote_id}",
            headers={
                "X-Transaction": self.key
            },
            timeout=self.parent.done_timeout
        )

# TODO: Check response?
