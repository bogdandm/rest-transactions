"use strict";

var _slicedToArray = function () { function sliceIterator(arr, i) { var _arr = []; var _n = true; var _d = false; var _e = undefined; try { for (var _i = arr[Symbol.iterator](), _s; !(_n = (_s = _i.next()).done); _n = true) { _arr.push(_s.value); if (i && _arr.length === i) break; } } catch (err) { _d = true; _e = err; } finally { try { if (!_n && _i["return"]) _i["return"](); } finally { if (_d) throw _e; } } return _arr; } return function (arr, i) { if (Array.isArray(arr)) { return arr; } else if (Symbol.iterator in Object(arr)) { return sliceIterator(arr, i); } else { throw new TypeError("Invalid attempt to destructure non-iterable instance"); } }; }();

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

function _toConsumableArray(arr) { if (Array.isArray(arr)) { for (var i = 0, arr2 = Array(arr.length); i < arr.length; i++) { arr2[i] = arr[i]; } return arr2; } else { return Array.from(arr); } }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

var Controller = function () {
    var Controller = function () {
        function Controller(sse) {
            _classCallCheck(this, Controller);

            this.name = "Controller";
            this.body = Controller._pattern.clone();

            this.sse_listener = new EventListener(sse, this);

            this.global_timeout = new ProgressBar("Global timeout", 0, function (v) {
                return formatTime(v, "s");
            });
            this.body.find("#controller_bars").append(this.global_timeout.body);
            this.controller_services_node = this.body.find("#controller_services");

            this.bulb_ugly = new (Function.prototype.bind.apply(Bulb, [null].concat(_toConsumableArray(Bulb.blue), [0.5, 10, "#bcbcbc"])))();
            this.body.find('._bulbs').append(this.bulb_ugly.body);

            this.bulb_good = new (Function.prototype.bind.apply(Bulb, [null].concat(_toConsumableArray(Bulb.green), [0.5, 10, "#bcbcbc"])))();
            this.body.find('._bulbs').append(this.bulb_good.body);

            this.bulb_bad = new (Function.prototype.bind.apply(Bulb, [null].concat(_toConsumableArray(Bulb.red), [0.5, 10, "#bcbcbc"])))();
            this.body.find('._bulbs').append(this.bulb_bad.body);

            if (Controller.main_node !== null) {
                Controller.main_node.append(this.body);
            }
            if (Controller.log_node !== null) {
                Controller.log_node.append(this.sse_listener.node);
            }

            this.controller_status = {};
            this.controller_status_body = this.body.find("#controller_status");
            this.controller_status_formatter = new JSONFormatter(this.controller_status, 10, {
                hoverPreviewEnabled: false,
                theme: '',
                animateOpen: false,
                animateClose: false
            });
            this.controller_status_timer = setInterval(this.updateStatus.bind(this), 1000, this);
        }

        _createClass(Controller, [{
            key: "updateStatus",
            value: function updateStatus() {
                var _this = this;

                var self = this;
                $.getJSON(globals.transaction_url, function (data) {
                    var _iteratorNormalCompletion = true;
                    var _didIteratorError = false;
                    var _iteratorError = undefined;

                    try {
                        for (var _iterator = Object.entries(data)[Symbol.iterator](), _step; !(_iteratorNormalCompletion = (_step = _iterator.next()).done); _iteratorNormalCompletion = true) {
                            var _step$value = _slicedToArray(_step.value, 2),
                                key = _step$value[0],
                                value = _step$value[1];

                            self.controller_status[key] = value;
                        }
                    } catch (err) {
                        _didIteratorError = true;
                        _iteratorError = err;
                    } finally {
                        try {
                            if (!_iteratorNormalCompletion && _iterator.return) {
                                _iterator.return();
                            }
                        } finally {
                            if (_didIteratorError) {
                                throw _iteratorError;
                            }
                        }
                    }

                    self.controller_status_body.empty().append(_this.controller_status_formatter.render());
                });
            }
        }, {
            key: "init",
            value: function init(data) {
                this.global_timeout.setMax(data.timeout);
                this.global_timeout.startTimer();
                var _iteratorNormalCompletion2 = true;
                var _didIteratorError2 = false;
                var _iteratorError2 = undefined;

                try {
                    for (var _iterator2 = data.actions[Symbol.iterator](), _step2; !(_iteratorNormalCompletion2 = (_step2 = _iterator2.next()).done); _iteratorNormalCompletion2 = true) {
                        var action = _step2.value;

                        var n = Number(action.service.url.match(/localhost:501([0-9])/)[1]);
                        var service = new Service("Service #" + n, action.service.timeout, "http://localhost:901" + n + "/debug_sse");
                        window.globals.services[action["_id"]] = service;

                        this.controller_services_node.append(service.cbody);
                        if (Controller.main_node !== null) {
                            Controller.main_node.append(service.body);
                        }
                        if (Controller.log_node !== null) {
                            Controller.log_node.append(service.sse_listener.node);
                        }
                    }
                } catch (err) {
                    _didIteratorError2 = true;
                    _iteratorError2 = err;
                } finally {
                    try {
                        if (!_iteratorNormalCompletion2 && _iterator2.return) {
                            _iterator2.return();
                        }
                    } finally {
                        if (_didIteratorError2) {
                            throw _iteratorError2;
                        }
                    }
                }
            }
        }, {
            key: "setStatus",
            value: function setStatus(status) {
                var _this2 = this;

                /*
                 case "ready_commit":
                 case "fail":
                 case "prepare_commit":
                 case "committed":
                 case "rollback":
                 */
                var panel = this.body.find(">.panel");

                (function () {
                    switch (status) {
                        case "open_connection":
                            _this2.bulb_ugly.turn_blink(false);
                            _this2.bulb_good.turn_blink(false);
                            _this2.bulb_bad.turn_blink(false);
                            panel.replaceClass("panel-", "panel-default");
                            break;

                        case "lost_connection":
                            var duration = 1500;
                            setTimeout(function () {
                                return _this2.bulb_ugly.turn_blink(duration);
                            }, 0);
                            setTimeout(function () {
                                return _this2.bulb_good.turn_blink(duration);
                            }, duration / 3);
                            setTimeout(function () {
                                return _this2.bulb_bad.turn_blink(duration);
                            }, 2 * duration / 3);
                            panel.replaceClass("panel-", "panel-warning");
                            break;

                        case "fail":
                            panel.replaceClass("panel-", "panel-danger");
                            _this2.global_timeout.stopTimer();
                            _this2.bulb_good.turn(false);
                            _this2.bulb_bad.turn();
                            break;

                        case "commit":
                            panel.replaceClass("panel-", "panel-primary");
                            _this2.bulb_good.turn_blink();
                            break;

                        case "finish":
                            clearInterval(_this2.controller_status_timer);
                            panel.replaceClass("panel-", "panel-success");
                            _this2.global_timeout.stopTimer();
                            _this2.bulb_ugly.turn();
                            _this2.bulb_good.turn();
                            break;

                        case "rollback":
                            panel.replaceClass("panel-", "panel-danger");
                            _this2.global_timeout.stopTimer();
                            _this2.bulb_ugly.turn();
                            _this2.bulb_good.turn(false);
                            _this2.bulb_bad.turn();
                            break;

                        default:
                            break;
                    }
                })();
            }
        }, {
            key: "event",
            value: function event(_event) {
                var service = void 0;
                var chid = void 0;
                this.bulb_ugly.blink();
                switch (_event.type) {
                    case "init":
                        this.init(_event.data);
                        break;

                    case "ready_commit":
                    case "fail":
                    case "commit":
                    case "rollback":
                    case "finish":
                        this.setStatus(_event.type);
                        break;

                    case "init_child":
                        break;

                    case "init_child_2":
                        chid = _event.data["chid"];
                        var pt = _event.data["ping-timeout"];
                        service = window.globals.services[chid];
                        break;

                    case "ping_child":
                    case "prepare_commit_child":
                        chid = _event.data;
                        service = window.globals.services[chid];
                        service.cbulb_ugly.blink();
                        break;

                    case "fail_child":
                    case "commit_child":
                    case "done_child":
                    case "rollback_child":
                        chid = _event.data;
                        service = window.globals.services[chid];
                        service.setCStatus(_event.type.replace("_child", ""));
                        break;

                    case "ready_commit_child":
                        chid = _event.data["chid"];
                        service = window.globals.services[chid];
                        service.setCStatus(_event.type.replace("_child", ""));
                        break;

                    default:
                        console.warn("Unhandled event", _event);
                }
            }
        }]);

        return Controller;
    }();

    var pattern = "\n        <div id=\"controller_status_wrapper\" class=\"panel-group\">\n            <div class=\"panel panel-default\">\n                <div id=\"controller_status\" class=\"panel-body\">-</div>\n            </div>\n        </div>\n        <div id=\"controller\" class=\"container col-md-4\">\n            <div class=\"panel panel-default\">\n                <div class=\"panel-heading flex-h\">\n                    <span class=\"_name\">Controller</span>\n                    <div class=\"_bulbs flex-h\"></div>\n                </div>\n                <div class=\"panel-body\">\n                    <div id=\"controller_bars\" class=\"panel-group\">\n                        <!-- ProgressBar -->\n                    </div>\n                    <div id=\"controller_services\" class=\"panel-group\">\n                        <!-- Services -->\n                    </div>\n                </div>\n            </div>\n        </div>\n    ";
    Controller._pattern = $(pattern);
    Controller.main_node = null;
    Controller.log_node = null;
    return Controller;
}();

//# sourceMappingURL=Controller.js.map