/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillStart, useRef, xml } from "@odoo/owl";

class StockCardReportBackend extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.contentRef = useRef("content");

        this.action = this.props.action || {};
        this.odooContext = this.action.context || {};
        this.givenContext = this.odooContext.context ? { ...this.odooContext.context } : {};

        this.givenContext.active_id =
            this.odooContext.active_id ||
            (this.action.params && this.action.params.active_id) ||
            false;
        this.givenContext.model = this.odooContext.active_model || false;
        this.givenContext.ttype = this.odooContext.ttype || false;

        this.html = "";

        onWillStart(async () => {
            await this._loadHtml();
        });

        onMounted(() => {
            this._renderHtml();
        });
    }

    async _loadHtml() {
        const result = await this.orm.call(
            this.givenContext.model,
            "get_html",
            [this.givenContext],
            { context: this.odooContext }
        );
        this.html = result.html || "";
    }

    _renderHtml() {
        if (!this.contentRef.el) {
            return;
        }

        this.contentRef.el.innerHTML = this.html;

        const printButton = this.contentRef.el.querySelector(".o_stock_card_reports_print");
        if (printButton) {
            printButton.addEventListener("click", this._onPrint.bind(this));
        }

        const exportButton = this.contentRef.el.querySelector(".o_stock_card_reports_export");
        if (exportButton) {
            exportButton.addEventListener("click", this._onExport.bind(this));
        }
    }

    async _onPrint(ev) {
        ev.preventDefault();
        const result = await this.orm.call(
            this.givenContext.model,
            "print_report",
            [this.givenContext.active_id, "qweb-pdf"],
            { context: this.odooContext }
        );
        this.actionService.doAction(result);
    }

    async _onExport(ev) {
        ev.preventDefault();
        const result = await this.orm.call(
            this.givenContext.model,
            "print_report",
            [this.givenContext.active_id, "xlsx"],
            { context: this.odooContext }
        );
        this.actionService.doAction(result);
    }
}

StockCardReportBackend.template = xml`
    <div class="o_stock_card_report_backend h-100 overflow-auto">
        <div t-ref="content"/>
    </div>
`;

registry.category("actions").add("stock_card_report_backend", StockCardReportBackend);
