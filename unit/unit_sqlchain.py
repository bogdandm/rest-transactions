from sqlite3 import connect
from unittest import TestCase

from sql_transactions import SqlChain
from tools import dict_factory


class Counter:
    def __init__(self):
        self.count = 1

    def __call__(self, *args, **kwargs):
        self.count += 1
        return ()

class SqlChainTest(TestCase):
    def setUp(self):
        self.connection = connect('chinook.db')
        self.connection.row_factory = dict_factory
        self.cursor = self.connection.cursor()

    def test_one_query(self):
        query = SqlChain("SELECT * FROM artists", cursor=self.cursor)
        query.execute()
        result = query.get()
        print(result)
        self.assertEqual(275, len(result))

    def test_chain(self):
        query1 = SqlChain("""SELECT * FROM artists WHERE Name LIKE '%stone%' LIMIT 1""", cursor=self.cursor)
        query2 = query1.chain("SELECT * FROM albums WHERE ArtistId=:id;",
                              vars_fn=lambda artist, *other: {"id": artist["ArtistId"]})
        query1.execute()
        print(query2.get())

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
        for i in range(100):
            ptr = ptr.chain(sql if i != stop - 1 else "SELECT * FROM DoesNotExists", vars_fn=counter)
        root.execute()
        result = ptr.get()
        print(result)
        self.assertEqual(counter.count, stop + 1)
        self.assertIsInstance(result, Exception)
