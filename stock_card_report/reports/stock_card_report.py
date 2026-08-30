# Copyright 2019 Ecosoft Co., Ltd. (http://ecosoft.co.th)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import datetime, time, timedelta

from odoo import api, fields, models


class StockCardView(models.TransientModel):
    _name = "stock.card.view"
    _description = "Stock Card View"
    _order = "date, id"

    date = fields.Datetime()
    product_id = fields.Many2one(comodel_name="product.product")
    product_qty = fields.Float()
    product_uom_qty = fields.Float()
    product_uom = fields.Many2one(comodel_name="uom.uom")
    reference = fields.Char()
    location_id = fields.Many2one(comodel_name="stock.location")
    location_dest_id = fields.Many2one(comodel_name="stock.location")
    is_initial = fields.Boolean()
    product_in = fields.Float()
    product_out = fields.Float()
    picking_id = fields.Many2one(comodel_name="stock.picking")
    move_id = fields.Many2one(comodel_name="stock.move")

    def _get_line_display_name(self):
        self.ensure_one()
        name = self.reference or ""
        if self.picking_id and self.picking_id.origin:
            name = "{} ({})".format(name, self.picking_id.origin)
        return name

    @api.depends("reference", "picking_id", "picking_id.origin")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec._get_line_display_name()


class StockCardReportLine(models.TransientModel):
    _name = "stock.card.report.line"
    _description = "Stock Card Report Line"
    _order = "product_id, date, id"

    report_id = fields.Many2one(
        comodel_name="report.stock.card.report",
        string="Report",
        required=True,
        ondelete="cascade",
    )
    date = fields.Datetime(string="Date")
    product_id = fields.Many2one(comodel_name="product.product", string="Product", readonly=True)
    product_categ_id = fields.Many2one(related="product_id.categ_id", string="Product Category", readonly=True, store=True)
    product_qty = fields.Float(string="Actual Quantity", readonly=True)
    product_uom_qty = fields.Float(string="Demand Quantity", readonly=True)
    product_uom = fields.Many2one(comodel_name="uom.uom", string="UoM", readonly=True)
    reference = fields.Char(string="Reference", readonly=True)
    display_reference = fields.Char(string="Display Reference", readonly=True)
    location_id = fields.Many2one(comodel_name="stock.location", string="Source Location", readonly=True)
    location_dest_id = fields.Many2one(comodel_name="stock.location", string="Destination Location", readonly=True)
    is_initial = fields.Boolean(string="Initial", readonly=True)
    product_in = fields.Float(string="In", readonly=True)
    product_out = fields.Float(string="Out", readonly=True)
    balance = fields.Float(string="Balance", readonly=True)
    picking_id = fields.Many2one(comodel_name="stock.picking", string="Picking", readonly=True)
    move_id = fields.Many2one(comodel_name="stock.move", string="Stock Move", readonly=True)

    @api.depends("display_reference", "reference", "product_id")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                rec.display_reference
                or rec.reference
                or rec.product_id.display_name
                or "Stock Card Line"
            )


class StockCardReport(models.TransientModel):
    _name = "report.stock.card.report"
    _description = "Stock Card Report"

    # Filters fields, used for data computation
    date_from = fields.Date()
    date_to = fields.Date()
    product_categ_ids = fields.Many2many(comodel_name="product.category")
    product_ids = fields.Many2many(comodel_name="product.product")
    location_id = fields.Many2one(comodel_name="stock.location")

    # Data fields, used to browse report data
    results = fields.Many2many(
        comodel_name="stock.card.view",
        compute="_compute_results",
        help="Use compute fields, so there is nothing store in database",
    )
    line_ids = fields.One2many(
        comodel_name="stock.card.report.line",
        inverse_name="report_id",
        string="Stock Card Lines",
        readonly=True,
    )

    def _get_locations(self):
        self.ensure_one()
        # If user selects a specific warehouse/location, report its child locations.
        # If left empty, report all internal warehouse locations.
        if self.location_id:
            return self.env["stock.location"].search(
                [("id", "child_of", [self.location_id.id])]
            )
        return self.env["stock.location"].search([("usage", "=", "internal")])

    def _date_to_datetime_start(self, date_value):
        return datetime.combine(date_value, time.min)

    def _date_to_datetime_next_day(self, date_value):
        return datetime.combine(date_value + timedelta(days=1), time.min)

    def _get_stock_card_values(self):
        self.ensure_one()
        date_from = self.date_from or fields.Date.from_string("0001-01-01")
        date_to = self.date_to or fields.Date.context_today(self)
        date_from_dt = self._date_to_datetime_start(date_from)
        date_to_dt = self._date_to_datetime_next_day(date_to)
        locations = self._get_locations()
        if not locations:
            return []

        location_ids = tuple(locations.ids)
        params = [
            location_ids,
            location_ids,
            date_from_dt,
            location_ids,
            location_ids,
        ]
        product_domain = []
        if self.product_ids:
            product_domain.append(("id", "in", self.product_ids.ids))
        if self.product_categ_ids:
            product_domain.append(("categ_id", "child_of", self.product_categ_ids.ids))

        product_filter = ""
        if product_domain:
            products = self.env["product.product"].search(product_domain)
            if not products:
                return []
            product_filter = "and move.product_id in %s"
            params.append(tuple(products.ids))
        params.append(date_to_dt)

        # Performance note:
        # Do not CAST(move.date AS date). Keeping direct datetime comparison allows
        # PostgreSQL to use indexes on stock_move.date/state/product/location columns.
        self._cr.execute(
            """
            SELECT move.date, move.product_id, move.quantity AS product_qty,
                move.product_uom_qty, move.product_uom, move.reference,
                move.location_id, move.location_dest_id,
                COALESCE(case when move.location_dest_id in %s
                    then move.quantity end, 0.0) as product_in,
                COALESCE(case when move.location_id in %s
                    then move.quantity end, 0.0) as product_out,
                case when move.date < %s then True else False end as is_initial,
                move.picking_id, move.id AS move_id
            FROM stock_move move
            WHERE (move.location_id in %s or move.location_dest_id in %s)
                and move.state = 'done'
                {product_filter}
                and move.date < %s
            ORDER BY move.product_id, move.date, move.reference, move.id
        """.format(product_filter=product_filter),
            tuple(params),
        )
        return self._cr.dictfetchall()

    def _compute_results(self):
        self.ensure_one()
        self.date_to = self.date_to or fields.Date.context_today(self)
        stock_card_results = self._get_stock_card_values()
        ReportLine = self.env["stock.card.view"]
        self.results = [ReportLine.new(line).id for line in stock_card_results]

    def _get_initial(self, product_line):
        product_input_qty = sum(product_line.mapped("product_in"))
        product_output_qty = sum(product_line.mapped("product_out"))
        return product_input_qty - product_output_qty

    def _get_report_products(self):
        self.ensure_one()
        if not self.line_ids:
            self.action_generate_lines()
        return self.line_ids.mapped("product_id").sorted(lambda product: product.display_name or "")

    def _get_product_lines(self, product):
        self.ensure_one()
        if not self.line_ids:
            self.action_generate_lines()
        return self.line_ids.filtered(lambda line: line.product_id == product).sorted(
            key=lambda line: (line.date or datetime.min, line.move_id.id or 0, line.id or 0)
        )

    def _get_display_reference_from_values(self, values):
        name = values.get("reference") or ""
        picking_id = values.get("picking_id")
        if picking_id:
            picking = self.env["stock.picking"].browse(picking_id)
            if picking.exists() and picking.origin:
                name = "{} ({})".format(name, picking.origin)
        return name

    def action_generate_lines(self):
        """Generate list/pivot lines without loading all stock moves in Python.

        Large stock-card ranges can return a huge number of move rows. The old
        implementation used ``dictfetchall()``, which loads the full result set
        into Odoo memory and can raise MemoryError. This method keeps the same
        output logic but lets PostgreSQL calculate the initial balance and
        running balance, then inserts rows directly in one SQL statement.
        """
        self.ensure_one()
        self.date_to = self.date_to or fields.Date.context_today(self)
        self.line_ids.unlink()

        date_from = self.date_from or fields.Date.from_string("0001-01-01")
        date_to = self.date_to or fields.Date.context_today(self)
        date_from_dt = self._date_to_datetime_start(date_from)
        date_to_dt = self._date_to_datetime_next_day(date_to)
        locations = self._get_locations()
        if not locations:
            return True

        location_ids = tuple(locations.ids)
        params = {
            "report_id": self.id,
            "uid": self.env.uid,
            "location_ids": location_ids,
            "date_from": date_from_dt,
            "date_to": date_to_dt,
        }

        product_domain = []
        if self.product_ids:
            product_domain.append(("id", "in", self.product_ids.ids))
        if self.product_categ_ids:
            product_domain.append(("categ_id", "child_of", self.product_categ_ids.ids))

        product_filter_sql = ""
        selected_product_sql = ""
        if product_domain:
            products = self.env["product.product"].search(product_domain)
            if not products:
                return True
            params["product_ids"] = tuple(products.ids)
            product_filter_sql = "AND move.product_id IN %(product_ids)s"
            selected_product_sql = "SELECT id AS product_id FROM product_product WHERE id IN %(product_ids)s UNION"

        sql = f"""
            WITH move_data AS (
                SELECT
                    move.id AS move_id,
                    move.date,
                    move.product_id,
                    move.quantity AS product_qty,
                    move.product_uom_qty,
                    move.product_uom,
                    move.reference,
                    move.location_id,
                    move.location_dest_id,
                    CASE
                        WHEN move.location_dest_id IN %(location_ids)s THEN move.quantity
                        ELSE 0.0
                    END AS product_in,
                    CASE
                        WHEN move.location_id IN %(location_ids)s THEN move.quantity
                        ELSE 0.0
                    END AS product_out,
                    move.picking_id,
                    picking.origin AS picking_origin
                FROM stock_move move
                LEFT JOIN stock_picking picking ON picking.id = move.picking_id
                WHERE (move.location_id IN %(location_ids)s OR move.location_dest_id IN %(location_ids)s)
                    AND move.state = 'done'
                    {product_filter_sql}
                    AND move.date < %(date_to)s
            ),
            products_scope AS (
                {selected_product_sql}
                SELECT DISTINCT product_id FROM move_data
            ),
            initial_data AS (
                SELECT
                    ps.product_id,
                    COALESCE(SUM(md.product_in - md.product_out), 0.0) AS initial_balance
                FROM products_scope ps
                LEFT JOIN move_data md
                    ON md.product_id = ps.product_id
                    AND md.date < %(date_from)s
                GROUP BY ps.product_id
            ),
            move_lines AS (
                SELECT
                    md.*,
                    COALESCE(idata.initial_balance, 0.0)
                    + SUM(md.product_in - md.product_out) OVER (
                        PARTITION BY md.product_id
                        ORDER BY md.date, md.reference, md.move_id
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) AS running_balance
                FROM move_data md
                JOIN initial_data idata ON idata.product_id = md.product_id
                WHERE md.date >= %(date_from)s
            )
            INSERT INTO stock_card_report_line (
                report_id,
                date,
                product_id,
                product_categ_id,
                product_qty,
                product_uom_qty,
                product_uom,
                reference,
                display_reference,
                location_id,
                location_dest_id,
                is_initial,
                product_in,
                product_out,
                balance,
                picking_id,
                move_id,
                create_uid,
                create_date,
                write_uid,
                write_date
            )
            SELECT
                %(report_id)s,
                NULL,
                idata.product_id,
                tmpl.categ_id,
                0.0,
                0.0,
                tmpl.uom_id,
                'Initial',
                'Initial',
                NULL,
                NULL,
                TRUE,
                0.0,
                0.0,
                idata.initial_balance,
                NULL,
                NULL,
                %(uid)s,
                NOW(),
                %(uid)s,
                NOW()
            FROM initial_data idata
            JOIN product_product product ON product.id = idata.product_id
            JOIN product_template tmpl ON tmpl.id = product.product_tmpl_id

            UNION ALL

            SELECT
                %(report_id)s,
                ml.date,
                ml.product_id,
                tmpl.categ_id,
                ml.product_qty,
                ml.product_uom_qty,
                ml.product_uom,
                ml.reference,
                CASE
                    WHEN ml.picking_origin IS NOT NULL AND ml.picking_origin != ''
                    THEN CONCAT(COALESCE(ml.reference, ''), ' (', ml.picking_origin, ')')
                    ELSE COALESCE(ml.reference, '')
                END,
                ml.location_id,
                ml.location_dest_id,
                FALSE,
                ml.product_in,
                ml.product_out,
                ml.running_balance,
                ml.picking_id,
                ml.move_id,
                %(uid)s,
                NOW(),
                %(uid)s,
                NOW()
            FROM move_lines ml
            JOIN product_product product ON product.id = ml.product_id
            JOIN product_template tmpl ON tmpl.id = product.product_tmpl_id
            ORDER BY 3, 2 NULLS FIRST, 17 NULLS FIRST
        """
        self._cr.execute(sql, params)
        self.env["stock.card.report.line"].invalidate_model()
        self.invalidate_recordset(["line_ids"])
        return True

    def action_view_lines(self):
        self.ensure_one()
        self.action_generate_lines()
        return {
            "type": "ir.actions.act_window",
            "name": "Stock Card Lines",
            "res_model": "stock.card.report.line",
            "view_mode": "list,pivot,graph",
            "domain": [("report_id", "=", self.id)],
            "context": {
                "search_default_group_by_product": 1,
                "pivot_measures": ["product_in", "product_out", "balance"],
            },
            "target": "current",
        }

    def print_report(self, report_type="qweb"):
        self.ensure_one()
        self.action_generate_lines()
        if report_type == "xlsx":
            return {
                "type": "ir.actions.act_url",
                "url": "/stock_card_report/export_xlsx_report/%s" % self.id,
                "target": "self",
            }
        action = self.env.ref("stock_card_report.action_stock_card_report_pdf")
        return action.report_action(self, config=False)

    def _get_html(self):
        result = {}
        rcontext = {}
        report = self.browse(self._context.get("active_id"))
        if report:
            report.action_generate_lines()
            rcontext["o"] = report
            result["html"] = self.env["ir.qweb"]._render(
                "stock_card_report.report_stock_card_report_html", rcontext
            )
        return result

    @api.model
    def get_html(self, given_context=None):
        return self.with_context(given_context)._get_html()
