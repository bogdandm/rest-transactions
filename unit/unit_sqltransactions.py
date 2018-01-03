import pyodbc
from typing import Iterable
from unittest import TestCase

from gevent import wait

from sql_transactions import CONNECTIONS
from sql_transactions.transactions import SqlChain, SqlTransaction, SqlResult
from tools import dict_factory


class Counter:
    def __init__(self):
        self.count = 1

    def __call__(self, *args, **kwargs):
        self.count += 1
        return ()


class SqlChainTest(TestCase):
    def setUp(self):
        self.connection = pyodbc.connect(CONNECTIONS.POSTGRE("test"))
        self.cursor = self.connection.cursor()

    def test_one_query(self):
        query = SqlChain("SELECT * FROM artists", cursor=self.cursor)
        query.execute()
        result = query.get()
        print(result)
        self.assertEqual(275, len(result))

    def test_chain(self):
        query1 = SqlChain("""SELECT * FROM artists WHERE Name ILIKE '%stone%' LIMIT 1""", cursor=self.cursor)
        query2 = query1.chain("SELECT * FROM albums WHERE ArtistId=?;",
                              vars_fn=lambda artist, *other: (artist["artistid"],))
        query1.execute()
        result = query2.get()
        print(result)
        self.assertEqual(result[0]["title"], 'Core')

    def test_long_chain(self):
        sql = "SELECT * FROM artists;"
        root = SqlChain(sql, cursor=self.cursor)
        ptr = root
        for i in range(100):
            ptr = ptr.chain(sql)
        root.execute()
        result = ptr.get()
        print(result)
        self.assertEqual(275, len(result))

    def test_long_chain_with_error_in_middle(self):
        counter = Counter()
        sql = "SELECT * FROM artists;"
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


class SqlTransactionTest(TestCase):
    def setUp(self):
        self.connection: pyodbc.Connection = pyodbc.connect(CONNECTIONS.POSTGRE("test"))
        self.connection2: pyodbc.Connection = pyodbc.connect(CONNECTIONS.POSTGRE("test"))

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

    def test_commit(self):
        cursor = self.cursor
        cursor.execute("SELECT COUNT(*) AS c FROM test;")
        row: dict = dict_factory(cursor, cursor.fetchone())
        self.assertFalse(row["c"])
        cursor.close()
        del cursor

        def result_processor(transaction: SqlTransaction, *results: Iterable[SqlResult]):
            return results

        sql = SqlChain("""INSERT INTO test(x, ch) VALUES (1, 'a'), (2, 'b')""", cursor=self.cursor)
        res_sql = sql.chain("""SELECT * FROM test;""")
        transaction = SqlTransaction(self.connection, result_processor)
        transaction.add(sql, result_container=res_sql)
        transaction.execute()
        wait((transaction.ready_commit,))
        res = transaction.get_result()
        self.assertEqual(len(res[0]), 2)

        cursor = self.connection2.cursor()
        cursor.execute("""SELECT * FROM test;""")
        self.assertEqual(len(cursor.fetchall()), 0)
        cursor.close()
        del cursor

        transaction.do_commit()
        wait((transaction.commit,))

        cursor = self.connection2.cursor()
        cursor.execute("""SELECT * FROM test;""")
        self.assertEqual(len(cursor.fetchall()), 2)
        cursor.close()

    def test_rollback(self):
        cursor = self.cursor
        cursor.execute("SELECT COUNT(*) AS c FROM test;")
        row: dict = dict_factory(cursor, cursor.fetchone())
        self.assertFalse(row["c"])
        cursor.close()
        del cursor

        def result_processor(transaction: SqlTransaction, *results: Iterable[SqlResult]):
            return results

        sql = SqlChain("""INSERT INTO test(x, ch) VALUES (1, 'a'), (2, 'a')""", cursor=self.cursor)
        res_sql = sql.chain("""SELECT * FROM test;""")
        transaction = SqlTransaction(self.connection, result_processor)
        transaction.add(sql, result_container=res_sql)
        transaction.execute()
        wait((transaction.ready_commit,))
        res = transaction.get_result()
        self.assertEqual(len(res[0]), 2)

        cursor = self.connection2.cursor()
        cursor.execute("""SELECT * FROM test;""")
        self.assertEqual(len(cursor.fetchall()), 0)
        cursor.close()
        del cursor

        transaction.do_rollback()
        wait((transaction.fail,))

        cursor = self.connection2.cursor()
        cursor.execute("""SELECT * FROM test;""")
        self.assertEqual(len(cursor.fetchall()), 0)
        cursor.close()
        del cursor
