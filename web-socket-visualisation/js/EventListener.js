"use strict";

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

var SseEvent = function () {
    return function () {
        function SseEvent(dict, parent) {
            _classCallCheck(this, SseEvent);

            this.parent = parent;
            this.type = dict.event;
            this.timeStamp = new Date(dict.t['@datetime'] * 1000);
            this.data = dict.data;
            this._view = new JSONFormatter(this.data, 0, {
                hoverPreviewEnabled: true,
                hoverPreviewArrayCount: 100,
                hoverPreviewFieldCount: 5,
                theme: '',
                animateOpen: false,
                animateClose: false
            });
        }

        _createClass(SseEvent, [{
            key: 'view',
            value: function view() {
                var text = function text(_text) {
                    return $("<td/>").text(_text);
                };
                var time = text(dateFormat(this.timeStamp, "HH:MM:ss.l"));
                var source = text(this.parent.name);
                var type = text(this.type);
                var json = $("<td/>").append(this._view.render());
                return $('<tr source=\'' + this.parent.name + '\'/>').append([time, source, type, json]).attr("metatype", this.type);
            }
        }]);

        return SseEvent;
    }();
}();

var EventListener = function () {
    var EventListener = function () {
        function EventListener(sse, parent) {
            var _this = this;

            _classCallCheck(this, EventListener);

            this.parent = parent;

            this.sse = sse;
            this.connection = new EventSource(sse);
            this.connection.parent = this;
            this.connection.onerror = function () {
                if (_this.parent && _this.parent.setStatus) _this.parent.setStatus("lost_connection");
            };
            this.connection.onopen = function () {
                if (_this.parent && _this.parent.setStatus) _this.parent.setStatus("open_connection");
            };
            this.connection.onmessage = this.onmsg;

            this.node = EventListener.pattern.clone();
            this.node.find(".panel-heading").text(parent.name);
            this.handlers = [];

            this.log = SortedList.create({
                compare: function compare(x, y) {
                    if (x.timeStamp > y.timeStamp) return 1;else if (x.timeStamp < y.timeStamp) return -1;else return 0;
                }
            });
        }

        _createClass(EventListener, [{
            key: 'close',
            value: function close() {
                this.connection.close();
            }
        }, {
            key: 'msg',
            value: function msg(f) {
                if (typeof f === "function") this.handlers.push(f);
            }
        }, {
            key: 'onmsg',
            value: function onmsg(e) {
                var self = void 0;
                if (this instanceof EventListener) self = this;else self = this.parent;
                var data = e.data;
                if (data === "INIT" || data === "PING") {
                    console.log(data);
                    return;
                }

                var event = new SseEvent(JSON.parse(data), self.parent);
                console.info(event);
                self.log.push(event);
                if (self.parent) self.parent.event(event);
                self.node.find('tbody').append(event.view());
                var _iteratorNormalCompletion = true;
                var _didIteratorError = false;
                var _iteratorError = undefined;

                try {
                    for (var _iterator = self.handlers[Symbol.iterator](), _step; !(_iteratorNormalCompletion = (_step = _iterator.next()).done); _iteratorNormalCompletion = true) {
                        var f = _step.value;

                        f(event);
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
            }
        }]);

        return EventListener;
    }();

    var pattern = '\n        <div class="panel panel-default">\n            <div class="panel-heading flex-h"></div>\n            <table class="table" cellspacing="0" width="100%">\n                <tbody>\n                    <tr>\n                        <th>Time</th>\n                        <th>Source</th>\n                        <th>Type</th>\n                        <th>Data</th>\n                    </tr>\n                </tbody>\n            </table>\n        </div>\n    ';
    EventListener.pattern = $(pattern);

    //EventListener.objects = {};
    return EventListener;
}();

//# sourceMappingURL=EventListener.js.map