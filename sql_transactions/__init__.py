import sqlite3
from typing import List, Set, Callable, Any, Dict, Iterable, Union, Tuple

from gevent.event import AsyncResult

from tools.gevent_ import g_async

SqlResult = Dict[str, Any]
VarsFnType = Callable[
    [Tuple[SqlResult, ...]],
    Union[Iterable, Dict[str, Any]]
]


class SqlChain(AsyncResult):
    def __init__(self, sql: str, vars: List = None, vars_fn: VarsFnType = None,
                 cursor: sqlite3.Cursor = None, parent: 'SqlChain' = None):
        super().__init__()
        self.sql = sql
        self.vars = vars
        self.vars_fn = vars_fn
        self.cursor = cursor or parent.cursor

        self.child: Set[SqlChain] = set()
        self.root = parent.root if parent else self
        self._nodes = {self} if self.is_root else None

    @property
    def is_root(self):
        return self.root is self

    @g_async
    def execute(self, parent_result: Iterable = ()):
        args = self.vars or (self.vars_fn(*parent_result) if self.vars_fn else ())
        try:
            self.cursor.execute(self.sql, args)
            result: Iterable[SqlResult] = self.cursor.fetchall()
            self.set(result)
            for ch in self.child:
                ch.execute(result)  # THREAD:1
        except sqlite3.Error as e:
            result = e
            for node in self.root._nodes:
                node.set(e)
            self.set(e)
        return result

    def chain(self, sql: str, *args, vars_fn: VarsFnType = None, **kwargs) -> 'SqlChain':
        new_node = self.__class__(sql=sql, parent=self, *args, **{"vars_fn": vars_fn, **kwargs})
        self.child.add(new_node)
        self.root._nodes.add(new_node)
        return new_node
