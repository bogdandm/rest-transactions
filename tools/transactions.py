from abc import ABCMeta, abstractmethod
from enum import Enum

from gevent import Greenlet
from gevent import event
from gevent.pool import Group

import tools
from tools.gevent import g_async


class EStatus(Enum):
    IN_PROGRESS = 1
    READY_COMMIT = 2
    FAIL = 3
    COMMIT = 4
    DONE = 5


tools.register_type(EStatus, (
    lambda s: str(s).split(".")[1],
    lambda s: EStatus[s]
))


class ATransaction(metaclass=ABCMeta):
    @abstractmethod
    def __init__(self, _id):
        self.id = _id
        self.main_thread: Greenlet = None
        self.threads = Group()
        self.ready_commit = event.Event()
        self.commit = event.Event()
        self.fail = event.Event()
        self.done = event.Event()
        self.result = event.AsyncResult()

    @property
    def status(self):
        if self.fail.ready():
            return EStatus.FAIL
        if self.done.ready():
            return EStatus.DONE
        if self.commit.ready():
            return EStatus.COMMIT
        if self.ready_commit.ready():
            return EStatus.READY_COMMIT
        return EStatus.IN_PROGRESS

    def run(self):
        self.main_thread = self._spawn()
        return self.main_thread

    @g_async
    def _spawn(self):
        pass

    @g_async
    def clean(self):
        self.main_thread.kill()
        self.threads.kill()

    @g_async
    def do_commit(self):
        pass

    @g_async
    def do_rollback(self):
        pass

    def get_result(self):
        return self.result.get()

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        return f"<ATransaction {self.id}>"

    def __str__(self):
        return f"ATransaction: #{self.id}"
