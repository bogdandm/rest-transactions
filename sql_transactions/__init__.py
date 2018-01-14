class CONNECTIONS:
    SQLITE = lambda db: "DRIVER={SQLite3};SERVER=localhost;DATABASE=%s;Trusted_connection=yes" % db
    POSTGRE = lambda db: "Driver={PostgreSQL};Server=127.0.0.1;Port=5432;Database=%s;UID=postgres;PWD=1234" % db
    MYSQL = lambda db: "Driver={MySQL ODBC 5.3 Unicode Driver};Database=%s;UID=root;PWD=1234" % db
