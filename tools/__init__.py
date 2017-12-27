import collections
import json
import logging
import numbers
import time
from base64 import b64encode, b64decode
from datetime import datetime
from enum import Enum
from typing import (Any, Union, TypeVar, Set, Dict, Tuple, Iterable, Generator, Sequence, MutableMapping, Callable)

from bson import ObjectId

KT = TypeVar('KT')
VT = TypeVar('VT')

Seconds = float


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def timeit(f):
    """
    Simple timer decorator

    :param f:
    :return:
    """

    def wrapper(*args, **kwargs):
        start = time.time()
        res = f(*args, **kwargs)
        end = time.time()
        print("{:.4f} s".format(end - start))
        return res, end - start

    return wrapper


def not_none(*args, default=None):
    """
    Return first True value. If all args is None return :default:

    >>> not_none({}, [], "", 0, default="All is None")
    'All is None'
    """
    return next(filter(None, args), default)


def dfilter(d: dict, *keys: Iterable, reverse=False) -> dict:
    """
    Filter dictionary (remove all items that not in keys). Create new dict.

    >>> dfilter({"a": 1, "b": 2, "c": 3}, "a")
    {'a': 1}

    >>> dfilter({"a": 1, "b": 2, "c": 3}, "a", reverse=True)
    {'b': 2, 'c': 3}

    :param d: dict
    :param keys: filter dict by keys
    :param reverse: if True remove items from dict that are in keys
    :return: new dict
    """
    return {k: v for k, v in d.items() if k in keys and not reverse or k not in keys and reverse}


def drename(d: dict, keys: dict, filter_=False):
    """
    Create new dict with renamed keys:

    >>> d = {'a': 1, 'b': 2, 'c': 3}
    >>> drename(d, {'a': 'a_1'})
    {'c': 3, 'b': 2, 'a_1': 1}
    >>> drename(d, {'a': 'a_1', 'd': 'd_4'}, filter_=True)
    {'a_1': 1}

    :param d:
    :param keys: Dict[key_to_rename => new_key]
    :param filter_:
    :return:
    """
    if filter_:
        res = {keys[k]: d[k] for k in keys if k in d}
    else:
        res = {(keys[k] if k in keys else k): v for k, v in d.items()}
    return res


def group(d: dict, *groups: str, delimiter="_"):
    """
    Replace dict items which are startwith any item from group. Create new dict

    >>> group({"A_1": True, "A_2": False}, "A")
    {'A': {'2': False, '1': True}}

    >>> group({"A|1": True, "A|2": False, "B|1": [], "B|2": {}}, "A", "B", delimiter="|")
    {'B': {'2': {}, '1': []}, 'A': {'2': False, '1': True}}

    :param d:
    :param groups:
    :param delimiter:
    :return:
    """
    res = d.copy()
    for g in groups:
        if g in res:
            res[g] = {None: res[g]}
        for k in d:
            if type(k) is str and k.startswith(g + delimiter):
                if g in res:
                    res[g][k.replace(g + delimiter, "")] = res[k]
                else:
                    res[g] = {k.replace(g + delimiter, ""): res[k]}
                del res[k]
    return res


def get_i(iterable: Iterable, i: int):
    """
    Yield each i-th item from iterables

    >>> list(get_i([(x, 2*x) for x in range(10)], 1))
    [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

    """
    for item in iterable:
        yield item[i]


def get_from_first(key: Any, *getters: Sequence, default: Any = None) -> Any:
    """
    Return first key => value from getters (see example)

    >>> get_from_first(2, {0: 'a', 1: 'b'}, ['a', 'b', 'c', 'd'])
    'c'

    :param key:
    :param getters:
    :param default:
    :return:
    """
    for item in getters:
        if item and (
                isinstance(item, dict) and key in item
                or isinstance(key, numbers.Integral) and hasattr(item, "__len__") and 0 <= int(key) < len(item)
        ):
            return item[key]
    return default


def rvg(g: Generator):
    # noinspection PyUnreachableCode
    """
    Get return value from generator

    >>> def f():
    ... 	return 1
    ... 	yield None
    ...
    >>> f()
    <generator object f at 0x02FB2600>
    >>> rvg(f())
    1

    """
    try:
        return next(g)
    except StopIteration as r:
        return r.value


# ================================================================ #

def _load_types():
    global _transform_types
    _transform_types = {'@' + t.__name__: t for t in _transform.keys()}


_transform = {
    datetime: (datetime.timestamp, datetime.fromtimestamp),
    bytes: (
        lambda v: b64encode(v, b"*-").replace(b"=", b"_").decode('utf-8'),
        lambda v: b64decode(v.replace("_", "="), b"*-")
    ),
    ObjectId: (str, ObjectId),
}

_transform_types = {}
_load_types()

T = TypeVar('T')


def register_type(type_, serializer_deserializer: Tuple[Callable[[T], str], Callable[[str], T]]):
    """
    Register new type to transform.

    :param type_: type
    :param serializer_deserializer: Tuple(serialisator, deserialisator)
    :return:
    """
    global _transform
    if type_ not in _transform:
        _transform[type_] = serializer_deserializer
        _load_types()


def transform_json_types(data: Union[dict, list], direction=0):
    """
    (De)serialized some types such datetime, bytes to valid json format

    >>> transform_json_types({"bytes": b"hello", "dt": datetime.now()})
    {'bytes': {'@bytes': 'aGVsbG8_'}, 'dt': {'@datetime': 1477939630.213201}}

    >>> transform_json_types({'bytes': {'@bytes': 'aGVsbG8_'}, 'dt': {'@datetime': 1477939630.213201}}, direction=1)
    {'bytes': b'hello', 'dt': datetime.datetime(2016, 10, 31, 21, 47, 10, 213201)}

    see <register_type()> to add your types

    :param data:
    :param direction:
    :return:
    """
    global _transform, _transform_types
    for k, v in data.items() if isinstance(data, dict) else enumerate(data):
        t = type(v)
        if t is list or t is dict and not (len(v) == 1 and next(iter(v.keys()), "").startswith("@")):
            transform_json_types(data[k], direction=direction)
            continue

        if not direction:
            if t in _transform:
                data[k] = {"@" + t.__name__: _transform[t][direction](v)}
        else:
            if t is dict:
                t = next(iter(v.keys()), None)
                if t in _transform_types:
                    data[k] = _transform[_transform_types[t]][direction](v[t])
    return data


# ================================================================ #

null = object()


class MultiDict(MutableMapping[KT, VT]):
    # TODO: docs
    def __init__(self, init_dict: Dict[KT, VT] = None):
        self._key_val = dict()  # type: Dict[KT, VT]
        self._val_id = dict()  # type: Dict[VT, ObjectId]
        self._id_keys = dict()  # type: Dict[ObjectId, Set[KT]]

        if init_dict is not None:
            for k, v in init_dict.items():
                self[k] = v

    def _full_val(self, *args, value: VT = null, key: KT = null, _id: ObjectId = null) \
            -> Tuple[ObjectId, Set[KT], VT]:
        if value is not null:
            _id = self._val_id[value]
            keys = self._id_keys[_id]
            return _id, keys, value
        if key is not null:
            value = self._key_val[key]
            _id = self._val_id[value]
            keys = self._id_keys[_id]
            return _id, keys, value
        if _id is not null:
            keys = self._id_keys[_id]
            value = self._key_val[next(iter(keys))]
            return _id, keys, value

    def __getitem__(self, key: KT) -> VT:
        return self._key_val[key]

    def get(self, key: KT, default: VT = None):
        return self._key_val.get(key, default)

    def __setitem__(self, key: KT, value: VT):
        try:
            old_id, old_keys, old_value = self._full_val(key=key)
        except KeyError:
            pass
        else:
            if old_value is value:
                return

            del self[key]

        try:
            old_id, old_keys, old_value = self._full_val(value=value)
        except KeyError:
            self._key_val[key] = value
            _id = self._val_id[value] = ObjectId()
            self._id_keys[_id] = {key}
        else:  # value exists
            self._key_val[key] = value
            self._id_keys[old_id].add(key)

    def __delitem__(self, key: KT):
        if key in self._key_val:
            old_id, old_keys, old_value = self._full_val(key=key)
            del self._key_val[key]
            old_keys.remove(key)
            if len(old_keys) == 0:
                self.remove(old_value)
        else:
            raise KeyError(key)

    def __len__(self) -> int:
        return self._val_id.__len__()

    def __iter__(self) -> Iterable[KT]:
        for val, _id in self._val_id.items():
            keys = self._id_keys[_id]
            yield keys

    def __contains__(self, item: VT) -> bool:
        return item in self._key_val

    def keys(self) -> Iterable[KT]:
        return collections.KeysView(self)

    def values(self) -> Iterable[VT]:
        return self._val_id.keys()

    def items(self) -> Iterable[Tuple[KT, VT]]:
        for keys in self.keys():
            k = next(iter(keys))
            yield keys, self._key_val[k]

    def remove(self, value: VT):
        if value in self._val_id:
            _id = self._val_id[value]
            for k in self._id_keys[_id]:
                del self._key_val[k]
            del self._id_keys[_id]
            del self._val_id[value]
        else:
            raise KeyError(value)

    def __repr__(self):
        return "<MultiDict {{{}}}>".format(", ".join(map(
            lambda k_v: "{}: {}".format(k_v[0], k_v[1].__repr__()),
            self.items()
        )))

    def __str__(self):
        return "{{{}}}".format(", ".join(map(
            lambda k_v: "{}: {}".format(k_v[0], k_v[1].__repr__()),
            self.items()
        )))


class LevelFilter(logging.Filter):
    def __init__(self, param):
        super().__init__()
        self.param = param

    def filter(self, record: logging.LogRecord) -> bool:
        if self.param is None:
            return True
        elif isinstance(self.param, str):
            return record.levelname == self.param
        elif isinstance(self.param, Iterable):
            return record.levelname in self.param
        return False


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class EnumEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.name
        return json.JSONEncoder.default(self, obj)
