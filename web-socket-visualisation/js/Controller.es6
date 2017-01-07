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

        setStatus(status) {
            let panel = this.body.find(">.panel");
            switch (status) {
                case "ready_commit":
                    panel.replaceClass("panel-", "panel-success");
                    this.bulb_good.turn(true);
                    break;

                case "fail":
                    panel.replaceClass("panel-", "panel-danger");
                    this.bulb_bad.turn(true);
                    break;

                default:
                    panel.replaceClass("panel-", "panel-primary");
                    break;
            }
        }

        init(data) {
            this.global_timeout.setMax(data.timeout);
            this.global_timeout.startTimer();
            for (let action of data.actions) {
                let service = new Service(
                    action.service.name, action.service.timeout,
                    `http://localhost:901${Number(action.service.name.split("#")[1])}/debug_sse`
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

        event(event) {
            let service;
            let chid;
            this.bulb_ugly.blink();
            switch (event.type) {
                case "init":
                    this.init(event.data);
                    break;

                case "init_child":
                    break;

                case "init_child_2":
                    chid = event.data["chid"];
                    let pt = event.data["ping-timeout"];
                    service = window.globals.services[chid];
                    break;

                case "ping_child":
                    chid = event.data;
                    service = window.globals.services[chid];
                    service.cbulb_ugly.blink();
                    break;

                case "fail_child":
                    chid = event.data;
                    service = window.globals.services[chid];
                    service.setCStatus("fail");
                    break;

                case "ready_commit_child":
                    chid = event.data["chid"];
                    service = window.globals.services[chid];
                    service.setCStatus("ready_commit");
                    break;

                case "fail":
                    this.setStatus("fail");
                    break;

                case "ready_commit":
                    this.setStatus("ready_commit");
                    break;
            }
        }
    };

    let pattern = `
        <div id="controller" class="container col-md-4">
            <div class="panel panel-primary">
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
