"use strict";

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

function _toConsumableArray(arr) { if (Array.isArray(arr)) { for (var i = 0, arr2 = Array(arr.length); i < arr.length; i++) { arr2[i] = arr[i]; } return arr2; } else { return Array.from(arr); } }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

var TransactionGenerator = function () {
    return function () {
        function TransactionGenerator() {
            _classCallCheck(this, TransactionGenerator);

            this.globalTimeout = 0;
            this.numberOfServices = 0;
            this.localTimeout = [0, 0];
            this.params_node = null;
            this.json_node = null;
            this._json = null;
        }

        _createClass(TransactionGenerator, [{
            key: "connect",
            value: function connect(params_node, json_node) {
                var _this = this;

                this.params_node = params_node;
                this.json_node = json_node;

                this.params_node.find("#i_gt").val(localStorage.getItem("generator_globalTimeout")).on("input", function (e) {
                    _this.globalTimeout = Number($(e.target).val());
                    localStorage.setItem("generator_globalTimeout", _this.globalTimeout);
                    _this.render();
                });
                this.params_node.find("#i_ns").val(localStorage.getItem("generator_numberOfServices")).on("input", function (e) {
                    _this.numberOfServices = Number($(e.target).val());
                    localStorage.setItem("generator_numberOfServices", _this.numberOfServices);
                    _this.render();
                });
                this.params_node.find("#i_lt0").val(localStorage.getItem("generator_localTimeout0")).on("input", function (e) {
                    _this.localTimeout[0] = Number($(e.target).val());
                    localStorage.setItem("generator_localTimeout0", _this.localTimeout[0]);
                    _this.render();
                });
                this.params_node.find("#i_lt1").val(localStorage.getItem("generator_localTimeout1")).on("input", function (e) {
                    _this.localTimeout[1] = Number($(e.target).val());
                    localStorage.setItem("generator_localTimeout1", _this.localTimeout[1]);
                    _this.render();
                });
            }
        }, {
            key: "_toJSON",
            value: function _toJSON() {
                return {
                    timeout: this.globalTimeout,
                    actions: [].concat(_toConsumableArray(TransactionGenerator.actionGenerator(this.numberOfServices, this.localTimeout)))
                };
            }
        }, {
            key: "render",
            value: function render() {
                this._json = null;
                this.json_node.text(JSON.stringify(this.json, null, 4));
            }
        }, {
            key: "json",
            get: function get() {
                if (this._json) {
                    return this._json;
                } else {
                    return this._json = this._toJSON();
                }
            }
        }], [{
            key: "actionGenerator",
            value: regeneratorRuntime.mark(function actionGenerator(number, localTimeout) {
                var i;
                return regeneratorRuntime.wrap(function actionGenerator$(_context) {
                    while (1) {
                        switch (_context.prev = _context.next) {
                            case 0:
                                i = 0;

                            case 1:
                                if (!(i < number)) {
                                    _context.next = 7;
                                    break;
                                }

                                _context.next = 4;
                                return TransactionGenerator.getAction(i, localTimeout);

                            case 4:
                                i++;
                                _context.next = 1;
                                break;

                            case 7:
                            case "end":
                                return _context.stop();
                        }
                    }
                }, actionGenerator, this);
            })
        }, {
            key: "getAction",
            value: function getAction(i, localTimeout) {
                var rndWord = choice(globals.words);
                return {
                    _id: "Service #" + i + " GET " + rndWord,
                    service: {
                        //name: `Service #${i}`,
                        url: "http://localhost:501" + i + "/api",
                        timeout: randInt.apply(undefined, _toConsumableArray(localTimeout))
                    },
                    url: "/" + rndWord,
                    method: "GET",
                    data: {},
                    headers: {}
                };
            }
        }]);

        return TransactionGenerator;
    }();
}();

//# sourceMappingURL=TransactionGenerator.js.map