import inspect
import sys
from abc import ABCMeta


class AException(Exception, metaclass=ABCMeta):
    code = None  # type: int
    n = None  # type: int
    desc = None  # type: str

    @property
    def data(self):
        if len(self.args):
            if len(self.args) == 1:
                return self.args[0]
            else:
                return self.args
        else:
            return None


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
    desc = "token required"


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
    import json

    print(json.dumps({k: repr(v) for k, v in catalog.items()}, indent=4))
