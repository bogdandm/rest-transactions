class CONNECTIONS:
    SQLITE = lambda db: "DRIVER={SQLite3};SERVER=localhost;DATABASE=%s;Trusted_connection=yes" % db
    POSTGRE = (lambda db:
    "Driver={PostgreSQL};Server=127.0.0.1;Port=5432;Database=%s;UID=postgres;PWD=qwerty12+" % db)
