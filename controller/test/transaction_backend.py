from controller.transaction_daemon.transaction_backend import Transaction

transaction_json = {
	"timeout": 10000,
	"actions": [
		{
			"_id": "id1",
			"service": {
				"url": "http://localhost:5000/api",
				"timeout": 10000
			},
			"url": "/echo",
			"method": "POST",
			"data": {
				"echo": "hello world"
			},
			"headers": {},
			"then": None
		}
	]
}

tr = Transaction(transaction_json)
tr.run().join()
print(tr.status)
