"use strict";

function formatTime(t, limit = "ms") {
    let map = [
        ['h', Math.floor(t / 360000)],
        ['m', Math.floor(t / 60000) % 60],
        ['s', Math.floor(t / 1000) % 60],
        ['ms', t % 1000]
    ];
    let result = "";
    for (let [k, v] of map) {
        if (v)
            result += v + k + " ";
        if (k === limit)
            break;
    }
    if (result == "") result = "0" + limit;
    return result.trim();
}

function logEvent(event) {
    let table = $("#log").find("tbody");
    table.append(event.view());
}

function randInt(min, max) {
    return Math.round(Math.random() * (max - min) + min)
}

function choice(array) {
    return array[randInt(0, array.length - 1)]
}

const EStatus = {
    IN_PROGRESS: 1,
    READY_COMMIT: 2,
    FAIL: 3,
    TIMEOUT: 4,
    COMMITTED: 5
};

(function ($) {
    $.fn.replaceClass = function (c1, c2) {
        this.removeClass(function (index, css) {
            return (css.match(`(^|\\s)${c1}\\S+`) || []).join(' ');
        }).addClass(c2);
        return this;
    };
}(jQuery));