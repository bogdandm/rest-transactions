import inspect
import sys
from abc import ABCMeta


class AException(Exception, metaclass=ABCMeta):
	code = None
	n = None
	desc = None

	@property
	def data(self):
		return self.args[0] if len(self.args) else None


class DbTypeException(AException):
	code = 400
	n = 10
	desc = "wrong db type"


class ParamsException(AException):
	code = 400
	n = 11
	desc = "request params is invalid"


class ParamsValueException(AException):
	code = 400
	n = 11
	desc = "wrong params values"


class NoTokenException(AException):
	code = 401
	n = 20
	desc = "token required"


class TokenExpiredException(AException):
	code = 401
	n = 21
	desc = "token is expired"


class BadTokenException(AException):
	code = 401
	n = 22
	desc = "bad token"


class PermissionsRequiredException(AException):
	code = 401
	n = 23
	desc = "bad token"


class NameUniqueException(AException):
	code = 412
	n = 30
	desc = "name is occupied"


class UnknownException(AException):
	code = 500
	n = 40
	desc = "something going wrong"


catalog = dict(inspect.getmembers(
	sys.modules[__name__],
	lambda c: inspect.isclass(c) and issubclass(c, AException) and c is not AException
))

if __name__ == '__main__':
	print(catalog)