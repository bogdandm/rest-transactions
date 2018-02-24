import pyodbc
from functools import partial
from random import randint
from typing import Iterable, Callable, Dict, Any
from unittest import TestCase

from gevent import wait
from mimesis import Personal

from sql_transactions import CONNECTIONS
from sql_transactions.transactions import SqlChain, SqlTransaction, SqlResult, RouteWrapperTransaction
from tools import dict_factory


class Counter:
    def __init__(self):
        self.count = 1

    def __call__(self, *args, **kwargs):
        self.count += 1
        return ()


class DbSetUp(TestCase):
    PERSONS_COUNT = 1000
    PERSON_MIN_MONEY = 1000

    @classmethod
    def setUpClass(cls: 'DbSetUp'):
        connection = pyodbc.connect(CONNECTIONS.MYSQL("test"))
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM person;")
            count = cursor.fetchone()[0]
        if count < cls.PERSONS_COUNT:
            person = Personal('en')
            with connection.cursor() as cursor:
                cursor.executemany(
                    """INSERT INTO person(name, surname, age, email) VALUES (?, ?, ?, ?)""",
                    [(person.name(), person.surname(), person.age(), person.email())
                     for _ in range(cls.PERSONS_COUNT - count)]
                )
                cursor.commit()
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM person_money")
            factory: Callable[[tuple], Dict[str, Any]] = partial(dict_factory, cursor)
        insert = []
        update = []
        for person in map(factory, cursor.fetchall()):
            diff = cls.PERSON_MIN_MONEY - person['money']
            while diff > 0:
                add = randint(50, diff + cls.PERSON_MIN_MONEY // 2)
                new_account = bool(randint(0, 1)) or person['money'] == 0
                if new_account:
                    insert.append((person['id'], add))
                else:
                    update.append((add, person['id']))
                diff -= add
        with connection.cursor() as cursor:
            if insert: cursor.executemany("""INSERT INTO bank_account(person, size) VALUES (?, ?)""", insert)
            if update: cursor.executemany("""UPDATE bank_account SET size = size + ? WHERE person = ? LIMIT 1""",
                                          update)
            cursor.commit()

    def setUp(self):
        self.connection = pyodbc.connect(CONNECTIONS.MYSQL("test"))
        self.cursor = self.connection.cursor()


class SqlChainTest(DbSetUp):
    def test_one_query(self):
        query = SqlChain("SELECT * FROM person", cursor=self.cursor)
        query.execute()
        result = query.get()
        print(result)
        self.assertEqual(self.PERSONS_COUNT, len(result))

    def test_chain(self):
        query1 = SqlChain("""SELECT * FROM person_money WHERE money = (SELECT MAX(money) FROM person_money) LIMIT 1;""",
                          cursor=self.cursor)
        query2 = query1.chain("SELECT SUM(size) AS money FROM bank_account WHERE person=?;",
                              vars_fn=lambda person, *other: (person["id"],))
        query1.execute()
        result = query2.get()
        print(result)
        self.assertGreater(result[0]["money"], 1000)

    def test_long_chain(self):
        sql = "SELECT * FROM person;"
        root = SqlChain(sql, cursor=self.cursor)
        ptr = root
        for i in range(100):
            ptr = ptr.chain(sql)
        root.execute()
        result = ptr.get()
        print(result)
        self.assertEqual(self.PERSONS_COUNT, len(result))

    def test_long_chain_with_error_in_middle(self):
        counter = Counter()
        sql = "SELECT * FROM person;"
        root = SqlChain(sql, cursor=self.cursor)
        ptr = root
        stop = 50
        for i in range(1, 100 + 1):
            ptr = ptr.chain(sql if i != stop else "SELECT * FROM DoesNotExists", vars_fn=counter)
        root.execute()
        result = ptr.get()
        print(result)
        self.assertEqual(counter.count, stop + 1)
        self.assertIsInstance(result, Exception)


class DbTestSetUp(TestCase):
    def setUp(self):
        self.connection: pyodbc.Connection = pyodbc.connect(CONNECTIONS.MYSQL("test"))
        self.connection2: pyodbc.Connection = pyodbc.connect(CONNECTIONS.MYSQL("test"))

        cur = self.cursor
        cur.execute("DELETE FROM test;")
        self.connection.commit()
        cur.close()

    def tearDown(self):
        self.connection.close()
        self.connection2.close()

    @property
    def cursor(self):
        return self.connection.cursor()


class SqlTransactionTest(DbTestSetUp):
    def test_commit(self):
        with self.cursor as cursor:
            cursor.execute("SELECT COUNT(*) AS c FROM test;")
            row: dict = dict_factory(cursor, cursor.fetchone())
            self.assertFalse(row["c"])

        def result_processor(transaction: SqlTransaction, *results: Iterable[SqlResult]):
            return results

        sql = SqlChain("""INSERT INTO test(id, x, ch) VALUES ('a', 1, 'a'), ('b', 2, 'b')""", cursor=self.cursor)
        res_sql = sql.chain("""SELECT * FROM test;""")
        transaction = SqlTransaction(self.connection, result_processor)
        transaction.add(sql, result_container=res_sql)
        transaction.run()
        wait((transaction.ready_commit,))
        res = transaction.get_result()
        self.assertEqual(len(res[0]), 2)

        with self.connection2.cursor() as cursor:
            cursor.execute("""SELECT * FROM test;""")
            self.assertEqual(len(cursor.fetchall()), 0)

        transaction.do_commit()
        wait((transaction.commit,))

        with self.connection2.cursor() as cursor:
            cursor.execute("""SELECT * FROM test;""")
            count = len(cursor.fetchall())
            self.assertEqual(count, 2)

    def test_rollback(self):
        with self.cursor as cursor:
            cursor.execute("SELECT COUNT(*) AS c FROM test;")
            row: dict = dict_factory(cursor, cursor.fetchone())
            self.assertFalse(row["c"])

        def result_processor(transaction: SqlTransaction, *results: Iterable[SqlResult]):
            return results

        sql = SqlChain("""INSERT INTO test(id, x, ch) VALUES ('a', 1, 'a'), ('b', 2, 'b')""", cursor=self.cursor)
        res_sql = sql.chain("""SELECT * FROM test;""")
        transaction = SqlTransaction(self.connection, result_processor)
        transaction.add(sql, result_container=res_sql)
        transaction.run()
        wait((transaction.ready_commit,))
        res = transaction.get_result()
        self.assertEqual(len(res[0]), 2)

        with self.connection2.cursor() as cursor:
            cursor.execute("""SELECT * FROM test;""")
            self.assertEqual(len(cursor.fetchall()), 0)

        transaction.do_rollback()
        wait((transaction.fail,))

        with self.connection2.cursor() as cursor:
            cursor.execute("""SELECT * FROM test;""")
            self.assertEqual(len(cursor.fetchall()), 0)


class RouteWrapperTransactionTest(DbTestSetUp):
    def test_commit(self):
        with self.cursor as cursor:
            cursor.execute("SELECT COUNT(*) AS c FROM test;")
            row: dict = dict_factory(cursor, cursor.fetchone())
            self.assertFalse(row["c"])

        def route(connection: pyodbc.Connection):
            sql = SqlChain("""INSERT INTO test(id, x, ch) VALUES ('a', 1, 'a'), ('b', 2, 'b')""", cursor=connection.cursor())
            res_sql = sql.chain("""SELECT * FROM test;""")
            sql.execute()
            return res_sql.get()

        transaction = RouteWrapperTransaction(self.connection)
        transaction.wrap(route)
        transaction.run()
        wait((transaction.ready_commit,))
        res = transaction.get_result()
        self.assertEqual(len(res), 2)

        with self.connection2.cursor() as cursor:
            cursor.execute("""SELECT * FROM test;""")
            self.assertEqual(len(cursor.fetchall()), 0)

        transaction.do_commit()
        wait((transaction.commit,))

        with self.connection2.cursor() as cursor:
            cursor.execute("""SELECT * FROM test;""")
            count = len(cursor.fetchall())
            self.assertEqual(count, 2)

    def test_rollback(self):
        with self.cursor as cursor:
            cursor.execute("SELECT COUNT(*) AS c FROM test;")
            row: dict = dict_factory(cursor, cursor.fetchone())
            self.assertFalse(row["c"])

        def route(connection: pyodbc.Connection):
            sql = SqlChain("""INSERT INTO test(id, x, ch) VALUES ('a', 1, 'a'), ('b', 2, 'b')""", cursor=connection.cursor())
            res_sql = sql.chain("""SELECT * FROM test;""")
            sql.execute()
            return res_sql.get()

        transaction = RouteWrapperTransaction(self.connection)
        transaction.wrap(route)
        transaction.run()
        wait((transaction.ready_commit,))
        res = transaction.get_result()
        self.assertEqual(len(res), 2)

        with self.connection2.cursor() as cursor:
            cursor.execute("""SELECT * FROM test;""")
            self.assertEqual(len(cursor.fetchall()), 0)

        transaction.do_rollback()
        wait((transaction.fail,))

        with self.connection2.cursor() as cursor:
            cursor.execute("""SELECT * FROM test;""")
            self.assertEqual(len(cursor.fetchall()), 0)
