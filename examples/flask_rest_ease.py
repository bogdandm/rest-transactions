from random import randint

from bson import ObjectId

from tools.exceptions import UnknownException
from tools.flask import EmptyApp
from tools.flask.decorators import json, validate, nocache


def main(port=5000):
    app = EmptyApp("./", "/api", False, True)

    schema1 = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "type": "object",
        "properties": {
            "x": {
                "type": "string"
            },
            "y": {
                "type": "string"
            }
        },
        "required": [
            "x",
            "y"
        ]
    }

    schema2 = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "type": "array",
        "items": {
            "type": "integer"
        }
    }

    @app.route("/sum", methods=["GET"])
    @validate(schema1)
    @json()
    def index_get(data):
        return {"result": int(data['x']) + int(data['y'])}

    @app.route("/sum", methods=["POST"])
    @validate(schema2)
    @json()
    def index_post(data):
        return {"result": sum(data)}

    @app.route("/random", methods=["POST"])
    @nocache
    @json(id_field="_id", hide_id=True)
    def random_post():
        return {"result": randint(0, 2 ** 100), "_id": str(ObjectId())}

    @app.route("/500")
    @json()
    def test500():
        return 1 / 0

    @app.route("/error")
    @json()
    def test_error():
        raise UnknownException()

    app.run(port=port)


if __name__ == '__main__':
    main()
