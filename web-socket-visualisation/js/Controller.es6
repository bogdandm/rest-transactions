"use strict";

const Controller = (function () {
    let Controller = class {
        constructor(sse) {
            this.name = "Controller";
            this.body = Controller._pattern.clone();

            this.sse_listener = new EventListener(sse, this);

            this.global_timeout = new ProgressBar("Global timeout", 0, (v) => formatTime(v, "s"));
            this.body.find("#controller_bars").append(this.global_timeout.body);
            this.controller_services_node = this.body.find("#controller_services");

            this.bulb_ugly = new Bulb(...Bulb.blue, 0.5, 10, "#bcbcbc");
            this.body.find('._bulbs').append(this.bulb_ugly.body);

            this.bulb_good = new Bulb(...Bulb.green, 0.5, 10, "#bcbcbc");
            this.body.find('._bulbs').append(this.bulb_good.body);

            this.bulb_bad = new Bulb(...Bulb.red, 0.5, 10, "#bcbcbc");
            this.body.find('._bulbs').append(this.bulb_bad.body);

            if (Controller.main_node !== null) {
                Controller.main_node.append(this.body);
            }
            if (Controller.log_node !== null) {
                Controller.log_node.append(this.sse_listener.node);
            }
        }

        init(data) {
            this.global_timeout.setMax(data.timeout);
            this.global_timeout.startTimer();
            for (let action of data.actions) {
                let n = Number(action.service.url.match(/localhost:501([0-9])/)[1]);
                let service = new Service(
                    "Service #" + n, action.service.timeout,
                    `http://localhost:901${n}/debug_sse`
                );
                window.globals.services[action["_id"]] = service;

                this.controller_services_node.append(service.cbody);
                if (Controller.main_node !== null) {
                    Controller.main_node.append(service.body);
                }
                if (Controller.log_node !== null) {
                    Controller.log_node.append(service.sse_listener.node);
                }
            }
        }

        setStatus(status) {
            /*
             case "ready_commit":
             case "fail":
             case "prepare_commit":
             case "committed":
             case "rollback":
             */
            let panel = this.body.find(">.panel");
            switch (status) {
                case "open_connection":
                    this.bulb_ugly.turn_blink(false);
                    this.bulb_good.turn_blink(false);
                    this.bulb_bad.turn_blink(false);
                    panel.replaceClass("panel-", "panel-default");
                    break;

                case "lost_connection":
                    const duration = 1500;
                    setTimeout(() => this.bulb_ugly.turn_blink(duration), 0);
                    setTimeout(() => this.bulb_good.turn_blink(duration), duration / 3);
                    setTimeout(() => this.bulb_bad.turn_blink(duration), 2 * duration / 3);
                    panel.replaceClass("panel-", "panel-warning");
                    break;

                case "fail":
                    panel.replaceClass("panel-", "panel-danger");
                    this.global_timeout.stopTimer();
                    this.bulb_good.turn(false);
                    this.bulb_bad.turn();
                    break;

                case "commit":
                    panel.replaceClass("panel-", "panel-primary");
                    this.bulb_good.turn_blink();
                    break;

                case "finish":
                    panel.replaceClass("panel-", "panel-success");
                    this.global_timeout.stopTimer();
                    this.bulb_ugly.turn();
                    this.bulb_good.turn();
                    break;

                case "rollback":
                    panel.replaceClass("panel-", "panel-danger");
                    this.global_timeout.stopTimer();
                    this.bulb_ugly.turn();
                    this.bulb_good.turn(false);
                    this.bulb_bad.turn();
                    break;

                default:
                    break;
            }
        }

        event(event) {
            let service;
            let chid;
            this.bulb_ugly.blink();
            switch (event.type) {
                case "init":
                    this.init(event.data);
                    break;

                case "ready_commit":
                case "fail":
                case "commit":
                case "rollback":
                case "finish":
                    this.setStatus(event.type);
                    break;

                case "init_child":
                    break;

                case "init_child_2":
                    chid = event.data["chid"];
                    let pt = event.data["ping-timeout"];
                    service = window.globals.services[chid];
                    break;

                case "ping_child":
                case "prepare_commit_child":
                    chid = event.data;
                    service = window.globals.services[chid];
                    service.cbulb_ugly.blink();
                    break;

                case "fail_child":
                case "commit_child":
                case "done_child":
                case "rollback_child":
                    chid = event.data;
                    service = window.globals.services[chid];
                    service.setCStatus(event.type.replace("_child", ""));
                    break;

                case "ready_commit_child":
                    chid = event.data["chid"];
                    service = window.globals.services[chid];
                    service.setCStatus(event.type.replace("_child", ""));
                    break;

                default:
                    console.warn("Unhandled event", event)
            }
        }
    };

    let pattern = `
        <div id="controller" class="container col-md-4">
            <div class="panel panel-default">
                <div class="panel-heading flex-h">
                    <span class="_name">Controller</span>
                    <div class="_bulbs flex-h"></div>
                </div>
                <div class="panel-body">
                    <div id="controller_bars" class="panel-group">
                        <!-- ProgressBar -->
                    </div>        
                    <div id="controller_services" class="panel-group">
                        <!-- Services -->
                    </div>
                </div>
            </div>
        </div>
    `;
    Controller._pattern = $(pattern);
    Controller.main_node = null;
    Controller.log_node = null;
    return Controller;
})();
