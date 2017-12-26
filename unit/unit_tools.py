import math
from copy import deepcopy
from typing import List
from unittest import TestCase

import gevent
from gevent.event import Event

import tools
from tools.gevent import g_async, Wait


class CoreUtilsTest(TestCase):
    def setUp(self):
        print(self._testMethodName)

    def tearDown(self):
        print("=-=")

    def test_not_none(self):
        self.assertEqual(tools.not_none([], "", (), {}, 0, default="None"), "None")
        self.assertEqual(tools.not_none([1], {2}), [1])
        self.assertEqual(tools.not_none({2}, [1]), {2})

    def test_dfilter(self):
        d = {"a": 1, "b": 2, "c": 3}
        self.assertDictEqual(tools.dfilter(d, "a"), {"a": 1})
        self.assertDictEqual(tools.dfilter(d, "a", "b"), {"a": 1, "b": 2})
        self.assertDictEqual(tools.dfilter(d, "a", "b", reverse=True), {"c": 3})

    def test_group(self):
        d = {"A.a": 1, "B.a": 2, "A.b": 3, "A.c": 4, "B.": 5, "B": -1, "C": -2}
        self.assertDictEqual(tools.group(d, "A", "B", delimiter='.'), {
            'A': {'a': 1, 'b': 3, 'c': 4},
            'B': {None: -1, 'a': 2, '': 5},
            'C': -2
        })

    def test_get_i(self):
        l = [(i, str(i)) for i in range(100)]
        l_i = [i for i in range(100)]
        l_s = [str(i) for i in range(100)]
        self.assertEqual(list(tools.get_i(l, 0)), l_i)
        self.assertEqual(list(tools.get_i(l, 1)), l_s)

    def test_get_from_first(self):
        self.assertEqual(tools.get_from_first(4, [0, 1, 2], [0, 1, 2, 3, 4]), 4)
        self.assertEqual(tools.get_from_first(
            None,
            {'a': 1, 'b': 2, 'c': 3},
            {'a': 1, 'b': 2, 'c': 3, 'd': 4, 'f': 5, None: -1}
        ), -1)
        self.assertEqual(tools.get_from_first(
            2,
            ['a', 'b'],
            {0: 'a', 1: 'b', 2: 'c', 'd': 4, 'f': 5, None: -1}
        ), 'c')
        self.assertEqual(tools.get_from_first(
            2,
            ['a', 'b', 'c-1'],
            {0: 'a', 1: 'b', 2: 'c', 'd': 4, 'f': 5, None: -1}
        ), 'c-1')

    def test_rvg(self):
        def y(x):
            if False:
                yield
            return x

        self.assertEqual(tools.rvg(y("abc")), "abc")

    def test_transform_json_types(self):
        d = {
            "int": 1,
            "str": "qwerty",
            "list": [1, 2, 3],
            "dict1": {"a": 1, "b": 2},
            "datetime": tools.datetime.now(),
            "byte": b"qwerty",
            "id": tools.ObjectId(),
            "dict2": None
        }
        d["dict2"] = d.copy()
        try:
            tools.json.dumps(d)
            self.fail()
        except TypeError:
            pass

        d2 = tools.transform_json_types(d)
        s = tools.json.dumps(d2, indent=2)
        print(s)
        self.assertDictEqual(d, tools.transform_json_types(d2, direction=1))

    def test1(self):
        d = {
            'date': tools.datetime.now(),
            '_id': tools.ObjectId(),
            'bytes': b"1234567890",
            'dict': {
                '_id': tools.ObjectId(),
                '_id2': tools.ObjectId()
            },
            'list': [b"1", b"2", b"3", b"4"],
            'many_dict': {
                '_id': tools.ObjectId(),
                'd': {
                    'a': 1,
                    'b': b'hello'
                },
                'd2': []
            }
        }
        d0 = deepcopy(d)
        tools.transform_json_types(d)
        tools.transform_json_types(d, direction=1)
        self.assertDictEqual(d0, d)

    def test_register_type(self):
        d = {"set": {1, 2, 3}}
        try:
            tools.json.dumps(tools.transform_json_types(d))
            self.fail()
        except TypeError:
            pass
        tools.register_type(set, (list, set))
        print(tools.json.dumps(tools.transform_json_types(d)))
        self.assertDictEqual(d, tools.transform_json_types(tools.transform_json_types(d), direction=1))

    def test_drename(self):
        d = {'hello': 1, 'world': 2, 'a': 3, 'b': 4}
        self.assertDictEqual(
            tools.drename(d, {'hello': 'Hello', 'world': 'World'}),
            {'Hello': 1, 'World': 2, 'a': 3, 'b': 4}
        )
        self.assertDictEqual(
            tools.drename(d, {'hello': 'Hello', 'world': 'World'}, filter_=True),
            {'Hello': 1, 'World': 2}
        )

    def test_multi_dict(self):
        d: tools.MultiDict = tools.MultiDict()
        x = object()
        y = object()
        d[1] = d[2] = x
        d['a'] = d['b'] = y
        self.assertDictEqual(
            {(1, 2): x, ('a', 'b'): y},
            {tuple(sorted(k)): v for k, v in d.items()}
        )

        del d[1]
        self.assertTrue(d[2] is x and d['b'] is y)
        d.remove(y)
        self.assertTrue(d[2] is x and not ('a' in d and 'b' in d))

    def test_Singleton(self):
        class A(metaclass=tools.Singleton):
            def __init__(self, x, y):
                self.x = x
                self.y = y

        a1 = A(1, 2)
        a2 = A(3, 4)
        self.assertTrue(a1 is a2 and a1.x == a2.x == 1)


class GEventTest(TestCase):
    def setUp(self):
        print(self._testMethodName)

    def tearDown(self):
        print("=-=")

    def test_g_async(self):
        @g_async
        def f1(x):
            res = 0
            for i in range(x):
                res += i
            return res

        @g_async
        def f2(x):
            res = 1
            for i in range(1, x + 1):
                res *= i
            return res

        res = f2(100)  # type: gevent.Greenlet
        gevent.joinall([f1(i) for i in range(10 ** 3, 2 * 10 ** 3)])
        gevent.wait((res,))
        print(res.value)
        self.assertEqual(res.value, math.factorial(100))

    def test_wait(self):
        e1 = [Event() for _ in range(10)]
        e2 = [Event() for _ in range(10)]

        @g_async
        def set_e(events: List[Event]):
            for e in events:
                e.set()
                gevent.sleep(0.2)

        res = []

        def then(e):
            res.append(1)

        w1 = Wait(e1, count=5)
        w2 = Wait(e2, then=then)

        set_e(e1)
        set_e(e2)

        gevent.wait((w1.result, w2.result))
        print(w1.result.get(), w2.result.get())
        self.assertEqual(len(w1.result.get()), 5)
        self.assertTrue(res)
