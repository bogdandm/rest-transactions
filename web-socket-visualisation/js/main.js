"use strict";

var _slicedToArray = function () { function sliceIterator(arr, i) { var _arr = []; var _n = true; var _d = false; var _e = undefined; try { for (var _i = arr[Symbol.iterator](), _s; !(_n = (_s = _i.next()).done); _n = true) { _arr.push(_s.value); if (i && _arr.length === i) break; } } catch (err) { _d = true; _e = err; } finally { try { if (!_n && _i["return"]) _i["return"](); } finally { if (_d) throw _e; } } return _arr; } return function (arr, i) { if (Array.isArray(arr)) { return arr; } else if (Symbol.iterator in Object(arr)) { return sliceIterator(arr, i); } else { throw new TypeError("Invalid attempt to destructure non-iterable instance"); } }; }();

function _toConsumableArray(arr) { if (Array.isArray(arr)) { for (var i = 0, arr2 = Array(arr.length); i < arr.length; i++) { arr2[i] = arr[i]; } return arr2; } else { return Array.from(arr); } }

function formatTime(t) {
    var limit = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : "ms";

    var map = [['h', Math.floor(t / 360000)], ['m', Math.floor(t / 60000) % 60], ['s', Math.floor(t / 1000) % 60], ['ms', t % 1000]];
    var result = "";
    var _iteratorNormalCompletion = true;
    var _didIteratorError = false;
    var _iteratorError = undefined;

    try {
        for (var _iterator = map[Symbol.iterator](), _step; !(_iteratorNormalCompletion = (_step = _iterator.next()).done); _iteratorNormalCompletion = true) {
            var _step$value = _slicedToArray(_step.value, 2),
                k = _step$value[0],
                v = _step$value[1];

            if (v) result += v + k + " ";
            if (k === limit) break;
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

    if (result == "") result = "0" + limit;
    return result.trim();
}

function logEvent(event) {
    var table = $("#log").find("tbody");
    table.append(event.view());
}

function randInt(min, max) {
    return Math.round(Math.random() * (max - min) + min);
}

function choice(array) {
    return array[randInt(0, array.length - 1)];
}

var EStatus = {
    IN_PROGRESS: 1,
    READY_COMMIT: 2,
    FAIL: 3,
    TIMEOUT: 4,
    COMMITTED: 5
};

function load(map) {
    var objs = new Map();
    $("[x-is]").each(function (i) {
        var self = $(this);
        var id = self.attr("id");
        var type = self.attr("x-is");

        var args = self.attr("x-args");
        if (args) args = JSON.parse(args);else args = [];
        var obj = new (Function.prototype.bind.apply(map[type], [null].concat(_toConsumableArray(args))))();

        var call = self.attr("x-call");
        if (call) {
            var func = call,
                _args = [];
            if (call.indexOf(",") !== -1) {
                call = call.split(",");
                func = call[0].trim();

                _args = JSON.parse(call[1].trim());
                if (!_args.length) _args = [_args];
            }
            obj[func].apply(obj, _toConsumableArray(_args));
        }

        self.replaceWith(obj.body);
        objs.set(id ? id : i, obj);
    });
    return objs;
}

(function ($) {
    $.fn.replaceClass = function (c1, c2) {
        this.removeClass(function (index, css) {
            return (css.match("(^|\\s)" + c1 + "\\S+") || []).join(' ');
        }).addClass(c2);
        return this;
    };
})(jQuery);

//# sourceMappingURL=main.js.map