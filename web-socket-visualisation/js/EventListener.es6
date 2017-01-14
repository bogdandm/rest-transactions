"use strict";

const SseEvent = (function () {
    return class SseEvent {
        constructor(dict, parent) {
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

        view() {
            let text = (text) => $("<td/>").text(text);
            let time = text(dateFormat(this.timeStamp, "HH:MM:ss.l"));
            let source = text(this.parent.name);
            let type = text(this.type);
            let json = $("<td/>").append(this._view.render());
            return $(`<tr source='${this.parent.name}'/>`)
                .append([time, source, type, json])
                .attr("metatype", this.type);
        }
    };
})();

const EventListener = (function () {
    let EventListener = class {
        constructor(sse, parent) {
            this.parent = parent;

            this.sse = sse;
            this.connection = new EventSource(sse);
            this.connection.parent = this;
            this.connection.onerror = () => {
                if (this.parent && this.parent.setStatus)
                    this.parent.setStatus("lost_connection")
            };
            this.connection.onopen = () => {
                if (this.parent && this.parent.setStatus)
                    this.parent.setStatus("open_connection")
            };
            this.connection.onmessage = this.onmsg;

            this.node = EventListener.pattern.clone();
            this.node.find(".panel-heading").text(parent.name);
            this.handlers = [];

            this.log = SortedList.create({
                compare: (x, y) => {
                    if (x.timeStamp > y.timeStamp) return 1;
                    else if (x.timeStamp < y.timeStamp) return -1;
                    else return 0;
                }
            });
        }

        close() {
            this.connection.close();
        }

        msg(f) {
            if (typeof f === "function")
                this.handlers.push(f);
        }

        onmsg(e) {
            let self;
            if (this instanceof EventListener)
                self = this;
            else
                self = this.parent;
            let data = e.data;
            if (data === "INIT" || data === "PING") {
                console.log(data);
                return;
            }

            let event = new SseEvent(JSON.parse(data), self.parent);
            console.info(event);
            self.log.push(event);
            if (self.parent) self.parent.event(event);
            self.node.find('tbody').append(event.view());
            for (let f of self.handlers) {
                f(event);
            }
        }
    };

    let pattern = `
        <div class="panel panel-default">
            <div class="panel-heading flex-h"></div>
            <table class="table" cellspacing="0" width="100%">
                <tbody>
                    <tr>
                        <th>Time</th>
                        <th>Source</th>
                        <th>Type</th>
                        <th>Data</th>
                    </tr>
                </tbody>
            </table>
        </div>
    `;
    EventListener.pattern = $(pattern);

    //EventListener.objects = {};
    return EventListener;
})();