# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import datetime, time, timedelta

from odoo import api, fields, models


class StockLocationCardReportLine(models.TransientModel):
    _name = "stock.location.card.report.line"
    _description = "Stock Location Card Report Line"
    _order = "location_id, product_categ_id, product_id, date, id"

    report_id = fields.Many2one(
        comodel_name="report.stock.location.card.report",
        string="Report",
        required=True,
        ondelete="cascade",
    )
    date = fields.Datetime(string="Date", readonly=True)
    location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Location",
        readonly=True,
        help="The location whose card/balance is being reported.",
    )
    product_id = fields.Many2one(comodel_name="product.product", string="Product", readonly=True)
    product_categ_id = fields.Many2one(
        comodel_name="product.category", string="Product Category", readonly=True
    )
    product_qty = fields.Float(string="Signed Quantity", readonly=True)
    product_uom_qty = fields.Float(string="Demand Quantity", readonly=True)
    product_uom = fields.Many2one(comodel_name="uom.uom", string="UoM", readonly=True)
    reference = fields.Char(string="Transaction Reference", readonly=True)
    source_document = fields.Char(string="Source Document", readonly=True)
    display_reference = fields.Char(string="Display Reference", readonly=True)
    source_location_id = fields.Many2one(
        comodel_name="stock.location", string="Source Location", readonly=True
    )
    dest_location_id = fields.Many2one(
        comodel_name="stock.location", string="Destination Location", readonly=True
    )
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
                or "Location Card Line"
            )


class StockLocationCardReport(models.TransientModel):
    _name = "report.stock.location.card.report"
    _description = "Stock Location Card Report"

    date_from = fields.Date()
    date_to = fields.Date()
    warehouse_ids = fields.Many2many(
        comodel_name="stock.warehouse",
        relation="stock_loc_card_report_wh_rel",
        column1="report_id",
        column2="warehouse_id",
    )
    location_ids = fields.Many2many(
        comodel_name="stock.location",
        relation="stock_loc_card_report_loc_rel",
        column1="report_id",
        column2="location_id",
    )
    product_categ_ids = fields.Many2many(
        comodel_name="product.category",
        relation="stock_loc_card_report_categ_rel",
        column1="report_id",
        column2="category_id",
    )
    product_ids = fields.Many2many(
        comodel_name="product.product",
        relation="stock_loc_card_report_product_rel",
        column1="report_id",
        column2="product_id",
    )
    line_ids = fields.One2many(
        comodel_name="stock.location.card.report.line",
        inverse_name="report_id",
        string="Stock Location Card Lines",
        readonly=True,
    )

    def _date_to_datetime_start(self, date_value):
        return datetime.combine(date_value, time.min)

    def _date_to_datetime_next_day(self, date_value):
        return datetime.combine(date_value + timedelta(days=1), time.min)

    def _get_locations(self):
        """Return locations included in the Location Card report.

        - selected locations include their child locations;
        - selected transit locations are respected even when a warehouse is selected;
        - selected warehouses restrict the default location set to each warehouse stock
          location and child internal locations;
        - no location selection means all internal warehouse locations.
        """
        self.ensure_one()
        Location = self.env["stock.location"]
        allowed_usage_domain = [("usage", "in", ["internal", "transit"])]

        if self.warehouse_ids:
            warehouse_locations = Location.search(
                [
                    ("id", "child_of", self.warehouse_ids.mapped("lot_stock_id").ids),
                    ("usage", "=", "internal"),
                ]
            )
        else:
            # Keep the existing default behavior: if no location is selected,
            # report internal locations only. Transit locations are added when
            # the user selects them explicitly in the wizard.
            warehouse_locations = Location.search([("usage", "=", "internal")])

        if self.location_ids:
            selected_locations = Location.search(
                [
                    ("id", "child_of", self.location_ids.ids),
                    *allowed_usage_domain,
                ]
            )
            if self.warehouse_ids:
                selected_transit_locations = selected_locations.filtered(lambda loc: loc.usage == "transit")
                selected_internal_locations = selected_locations.filtered(lambda loc: loc.usage == "internal")
                return (selected_internal_locations & warehouse_locations) | selected_transit_locations
            return selected_locations
        return warehouse_locations

    def _get_product_domain(self):
        self.ensure_one()
        product_domain = []
        if self.product_ids:
            product_domain.append(("id", "in", self.product_ids.ids))
        if self.product_categ_ids:
            product_domain.append(("categ_id", "child_of", self.product_categ_ids.ids))
        return product_domain

    def _get_product_filter_sql(self, params):
        product_domain = self._get_product_domain()
        if not product_domain:
            return "", True
        products = self.env["product.product"].search(product_domain)
        if not products:
            return "", False
        params["product_ids"] = tuple(products.ids)
        return "AND move.product_id IN %(product_ids)s", True

    def action_generate_lines(self):
        """Generate one stock-card ledger per location and product.

        Each done stock move is split into two possible report sides:
        - source location side: Out / negative quantity;
        - destination location side: In / positive quantity.
        This keeps internal transfers visible on both affected locations.
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

        params = {
            "report_id": self.id,
            "uid": self.env.uid,
            "location_ids": tuple(locations.ids),
            "allowed_company_ids": tuple(self.env.companies.ids),
            "date_from": date_from_dt,
            "date_to": date_to_dt,
        }
        product_filter_sql, has_products = self._get_product_filter_sql(params)
        if not has_products:
            return True

        sql = f"""
            WITH raw_moves AS (
                SELECT
                    move.id AS move_id,
                    move.date,
                    move.product_id,
                    move.quantity AS quantity,
                    move.product_uom_qty,
                    move.product_uom,
                    move.reference,
                    move.origin AS move_origin,
                    move.location_id AS source_location_id,
                    move.location_dest_id AS dest_location_id,
                    move.picking_id,
                    picking.origin AS picking_origin
                FROM stock_move move
                LEFT JOIN stock_picking picking ON picking.id = move.picking_id
                WHERE move.state = 'done'
                    AND move.date < %(date_to)s
                    AND (move.company_id IS NULL OR move.company_id IN %(allowed_company_ids)s)
                    AND (
                        move.location_id IN %(location_ids)s
                        OR move.location_dest_id IN %(location_ids)s
                    )
                    {product_filter_sql}
            ),
            move_sides AS (
                SELECT
                    rm.move_id,
                    rm.date,
                    rm.product_id,
                    -rm.quantity AS signed_qty,
                    rm.quantity AS product_qty,
                    rm.product_uom_qty,
                    rm.product_uom,
                    rm.reference,
                    COALESCE(NULLIF(rm.picking_origin, ''), NULLIF(rm.move_origin, ''), '') AS source_document,
                    rm.source_location_id,
                    rm.dest_location_id,
                    rm.source_location_id AS report_location_id,
                    0.0 AS product_in,
                    rm.quantity AS product_out,
                    rm.picking_id,
                    1 AS side_order
                FROM raw_moves rm
                WHERE rm.source_location_id IN %(location_ids)s

                UNION ALL

                SELECT
                    rm.move_id,
                    rm.date,
                    rm.product_id,
                    rm.quantity AS signed_qty,
                    rm.quantity AS product_qty,
                    rm.product_uom_qty,
                    rm.product_uom,
                    rm.reference,
                    COALESCE(NULLIF(rm.picking_origin, ''), NULLIF(rm.move_origin, ''), '') AS source_document,
                    rm.source_location_id,
                    rm.dest_location_id,
                    rm.dest_location_id AS report_location_id,
                    rm.quantity AS product_in,
                    0.0 AS product_out,
                    rm.picking_id,
                    2 AS side_order
                FROM raw_moves rm
                WHERE rm.dest_location_id IN %(location_ids)s
            ),
            product_location_scope AS (
                SELECT DISTINCT report_location_id, product_id
                FROM move_sides
            ),
            initial_data AS (
                SELECT
                    pls.report_location_id,
                    pls.product_id,
                    COALESCE(SUM(ms.product_in - ms.product_out), 0.0) AS initial_balance
                FROM product_location_scope pls
                LEFT JOIN move_sides ms
                    ON ms.report_location_id = pls.report_location_id
                    AND ms.product_id = pls.product_id
                    AND ms.date < %(date_from)s
                GROUP BY pls.report_location_id, pls.product_id
            ),
            move_lines AS (
                SELECT
                    ms.*,
                    COALESCE(idata.initial_balance, 0.0)
                    + SUM(ms.product_in - ms.product_out) OVER (
                        PARTITION BY ms.report_location_id, ms.product_id
                        ORDER BY ms.date, ms.reference, ms.move_id, ms.side_order
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) AS running_balance
                FROM move_sides ms
                JOIN initial_data idata
                    ON idata.report_location_id = ms.report_location_id
                    AND idata.product_id = ms.product_id
                WHERE ms.date >= %(date_from)s
            )
            INSERT INTO stock_location_card_report_line (
                report_id,
                date,
                location_id,
                product_id,
                product_categ_id,
                product_qty,
                product_uom_qty,
                product_uom,
                reference,
                source_document,
                display_reference,
                source_location_id,
                dest_location_id,
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
                idata.report_location_id,
                idata.product_id,
                tmpl.categ_id,
                0.0,
                0.0,
                tmpl.uom_id,
                'Initial',
                '',
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
                ml.report_location_id,
                ml.product_id,
                tmpl.categ_id,
                ml.signed_qty,
                ml.product_uom_qty,
                ml.product_uom,
                COALESCE(ml.reference, ''),
                COALESCE(ml.source_document, ''),
                CASE
                    WHEN COALESCE(ml.source_document, '') != ''
                    THEN CONCAT(COALESCE(ml.reference, ''), ' (', ml.source_document, ')')
                    ELSE COALESCE(ml.reference, '')
                END,
                ml.source_location_id,
                ml.dest_location_id,
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
            ORDER BY 3, 5, 4, 2 NULLS FIRST, 19 NULLS FIRST
        """
        self._cr.execute(sql, params)
        self.env["stock.location.card.report.line"].invalidate_model()
        self.invalidate_recordset(["line_ids"])
        return True

    def _ensure_lines(self):
        self.ensure_one()
        if not self.line_ids:
            self.action_generate_lines()

    def _get_report_locations(self):
        self.ensure_one()
        self._ensure_lines()
        return self.line_ids.mapped("location_id").sorted(lambda loc: loc.complete_name or loc.display_name or "")

    def _get_location_categories(self, location):
        self.ensure_one()
        self._ensure_lines()
        return self.line_ids.filtered(lambda line: line.location_id == location).mapped(
            "product_categ_id"
        ).sorted(lambda categ: categ.complete_name or categ.display_name or "")

    def _get_location_category_products(self, location, category):
        self.ensure_one()
        self._ensure_lines()
        return self.line_ids.filtered(
            lambda line: line.location_id == location and line.product_categ_id == category
        ).mapped("product_id").sorted(lambda product: product.display_name or "")

    def _get_location_product_lines(self, location, product):
        self.ensure_one()
        self._ensure_lines()
        return self.line_ids.filtered(
            lambda line: line.location_id == location and line.product_id == product
        ).sorted(key=lambda line: (line.date or datetime.min, line.move_id.id or 0, line.id or 0))

    def action_view_lines(self):
        self.ensure_one()
        self.action_generate_lines()
        return {
            "type": "ir.actions.act_window",
            "name": "Location Card Lines",
            "res_model": "stock.location.card.report.line",
            "view_mode": "list,pivot,graph",
            "domain": [("report_id", "=", self.id)],
            "context": {
                "search_default_group_by_location": 1,
                "search_default_group_by_product": 1,
                "pivot_measures": ["product_in", "product_out", "balance", "product_qty"],
            },
            "target": "current",
        }

    def print_report(self, report_type="qweb-pdf"):
        self.ensure_one()
        self.action_generate_lines()
        if report_type == "xlsx":
            return {
                "type": "ir.actions.act_url",
                "url": "/stock_card_report/location_export_xlsx_report/%s" % self.id,
                "target": "self",
            }
        action = self.env.ref("stock_card_report.action_stock_location_card_report_pdf")
        return action.report_action(self, config=False)

    def _get_html(self):
        result = {}
        rcontext = {}
        report = self.browse(self._context.get("active_id"))
        if report:
            report.action_generate_lines()
            rcontext["o"] = report
            result["html"] = self.env["ir.qweb"]._render(
                "stock_card_report.report_stock_location_card_report_html", rcontext
            )
        return result

    @api.model
    def get_html(self, given_context=None):
        return self.with_context(given_context)._get_html()
