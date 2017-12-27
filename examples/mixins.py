from abc import ABCMeta, abstractmethod


class Abstract(metaclass=ABCMeta):
    def __init__(self, _id):
        self.id = _id

    @abstractmethod
    def foo(self):
        pass


class A(Abstract):
    def foo(self):
        return self.id[::-1]


class B(Abstract):
    def foo(self):
        return self.id[::2]


class Mixin(Abstract):
    def __init__(self, _id):
        super().__init__(_id)
        self.key = self.id.upper()

    def foo(self):
        return super(Mixin, self).foo() + self.key


class AMix(Mixin, A):
    pass


class BMix(Mixin, B):
    pass


if __name__ == '__main__':
    print(AMix("qwerty").foo())
    print(BMix("qwerty").foo())
