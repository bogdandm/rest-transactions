import numbers
import time
from base64 import b64encode, b64decode
from datetime import datetime
from typing import Iterable, Union, Any, Iterator, List, Tuple, Callable

from bson import ObjectId
from mysql.connector import IntegrityError


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
		return res

	return wrapper


def not_none(*args, default=None):
	"""
	Return first True value. If all args is None return :default:

	>>> not_none({}, [], "", 0, default="All is None")
	'All is None'
	"""
	for arg in args:
		if arg:
			return arg
	else:
		return default


def dfilter(d: dict, *keys: Iterable, reverse=False) -> dict:
	"""
	Filter dictionary (remove all items that not in keys).

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


def group(d: dict, *groups: List[str], delimiter="_"):
	"""
	replace dict items which are startwith any item from group

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
	Yield each i-th item from iterable

	>>> list(get_i([(x, 2*x) for x in range(10)], 1))
	[0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

	"""
	for item in iterable:
		yield item[i]


def get_from_first(key, *getters) -> Any:
	"""
	Return first key => value from getters (see example)

	>>> get_from_first(2, {0: 'a', 1: 'b'}, ['a', 'b', 'c', 'd'])
	'c'

	:param key:
	:param getters:
	:return:
	"""
	for item in getters:
		if item and isinstance(item, Iterable) and (isinstance(item, dict) and key in item
													or isinstance(key, numbers.Number) and 0 <= key < len(item)):
			return item[key]
	return None


def rvg(g: Iterator):
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
	except IntegrityError:
		return None


# ================================================================ #

def _load_types():
	global _transform_types
	_transform_types = dict(map(lambda t: ('@' + t.__name__, t), _transform.keys()))


_transform = {
	datetime: (lambda v: v.timestamp(), lambda v: datetime.fromtimestamp(v)),
	bytes: (
		lambda v: b64encode(v, b"*-").replace(b"=", b"_").decode('utf-8'),
		lambda v: b64decode(v.replace("_", "="), b"*-")
	),
	ObjectId: (str, ObjectId),
}

_transform_types = {}
_load_types()


def register_type(t, l: Tuple[Callable, Callable]):
	"""
	Register new type to transform.

	:param t: type
	:param l: Tuple(serialisator, deserialisator)
	:return:
	"""
	global _transform
	if t not in _transform:
		_transform[t] = l
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
		if t is list or t is dict and (len(v) > 1 or not next(v.keys().__iter__()).startswith("@")):
			transform_json_types(data[k], direction=direction)
			continue

		if not direction:
			if t in _transform:
				data[k] = {"@" + t.__name__: _transform[t][direction](v)}
		else:
			if t is dict:
				t = next(v.keys().__iter__())
				if t in _transform_types:
					data[k] = _transform[_transform_types[t]][direction](v[t])
	return data
