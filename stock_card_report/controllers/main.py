import io

from odoo import fields, http
from odoo.http import request

try:
    import xlsxwriter
except ImportError:  # pragma: no cover
    xlsxwriter = None


class StockCardReportXlsxController(http.Controller):

    def _xlsx_response(self, output, filename):
        output.seek(0)
        return request.make_response(
            output.read(),
            headers=[
                (
                    "Content-Type",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
                ("Content-Disposition", "attachment; filename=%s" % filename),
            ],
        )

    def _build_stock_card_xlsx(self, report):
        report.action_generate_lines()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Stock Card")

        title_format = workbook.add_format({"bold": True, "font_size": 18, "font_color": "#000000"})
        label_format = workbook.add_format({"bold": True, "font_size": 12, "font_color": "#000000"})
        text_format = workbook.add_format({"font_size": 12, "font_color": "#000000"})
        header_format = workbook.add_format({
            "bold": True,
            "font_size": 12,
            "font_color": "#000000",
            "bg_color": "#D9EAD3",
            "border": 1,
            "border_color": "#000000",
        })
        date_format = workbook.add_format({
            "font_size": 12,
            "font_color": "#000000",
            "num_format": "yyyy-mm-dd hh:mm:ss",
        })
        number_format = workbook.add_format({
            "font_size": 12,
            "font_color": "#000000",
            "num_format": "#,##0.000",
        })

        worksheet.write(0, 0, "Stock Card Report", title_format)
        worksheet.write(1, 0, "Date From", label_format)
        worksheet.write(1, 1, str(report.date_from or ""), text_format)
        worksheet.write(1, 2, "Date To", label_format)
        worksheet.write(1, 3, str(report.date_to or ""), text_format)
        worksheet.write(2, 0, "Warehouses", label_format)
        worksheet.write(2, 1, report.location_id.display_name if report.location_id else "All Warehouses", text_format)
        worksheet.write(3, 0, "Product Categories", label_format)
        worksheet.write(3, 1, ", ".join(report.product_categ_ids.mapped("display_name")) if report.product_categ_ids else "All Categories", text_format)

        headers = [
            "Date",
            "Product",
            "Product Category",
            "Reference",
            "Source Location",
            "Destination Location",
            "In",
            "Out",
            "Balance",
            "UoM",
            "Picking",
            "Stock Move",
        ]
        start_row = 5
        for col, header in enumerate(headers):
            worksheet.write(start_row, col, header, header_format)

        row = start_row + 1
        for line in report.line_ids:
            if line.date:
                worksheet.write_datetime(row, 0, line.date, date_format)
            else:
                worksheet.write(row, 0, "", text_format)
            worksheet.write(row, 1, line.product_id.display_name or "", text_format)
            worksheet.write(row, 2, line.product_categ_id.display_name or "", text_format)
            worksheet.write(row, 3, line.display_reference or line.reference or "", text_format)
            worksheet.write(row, 4, line.location_id.display_name or "", text_format)
            worksheet.write(row, 5, line.location_dest_id.display_name or "", text_format)
            worksheet.write_number(row, 6, line.product_in or 0.0, number_format)
            worksheet.write_number(row, 7, line.product_out or 0.0, number_format)
            worksheet.write_number(row, 8, line.balance or 0.0, number_format)
            worksheet.write(row, 9, line.product_uom.display_name or "", text_format)
            worksheet.write(row, 10, line.picking_id.display_name or "", text_format)
            worksheet.write(row, 11, line.move_id.display_name or "", text_format)
            row += 1

        worksheet.set_row(0, 24)
        worksheet.set_column(0, 0, 18)
        worksheet.set_column(1, 5, 28)
        worksheet.set_column(6, 8, 14)
        worksheet.set_column(9, 11, 20)
        workbook.close()
        return output

    def _build_location_card_xlsx(self, report):
        report.action_generate_lines()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Location Card")

        title_format = workbook.add_format({"bold": True, "font_size": 18, "font_color": "#000000"})
        label_format = workbook.add_format({"bold": True, "font_size": 12, "font_color": "#000000"})
        text_format = workbook.add_format({"font_size": 12, "font_color": "#000000"})
        section_format = workbook.add_format({
            "bold": True,
            "font_size": 12,
            "font_color": "#000000",
            "bg_color": "#E9ECEF",
            "border": 1,
            "border_color": "#000000",
        })
        header_format = workbook.add_format({
            "bold": True,
            "font_size": 12,
            "font_color": "#000000",
            "bg_color": "#D9EAD3",
            "border": 1,
            "border_color": "#000000",
        })
        date_format = workbook.add_format({
            "font_size": 12,
            "font_color": "#000000",
            "num_format": "yyyy-mm-dd hh:mm:ss",
        })
        number_format = workbook.add_format({
            "font_size": 12,
            "font_color": "#000000",
            "num_format": "#,##0.000",
        })

        worksheet.write(0, 0, "Location Card Report", title_format)
        worksheet.write(1, 0, "Date From", label_format)
        worksheet.write(1, 1, str(report.date_from or ""), text_format)
        worksheet.write(1, 2, "Date To", label_format)
        worksheet.write(1, 3, str(report.date_to or ""), text_format)
        worksheet.write(2, 0, "Warehouses", label_format)
        worksheet.write(2, 1, ", ".join(report.warehouse_ids.mapped("display_name")) if report.warehouse_ids else "All Warehouses", text_format)
        worksheet.write(3, 0, "Locations", label_format)
        worksheet.write(3, 1, ", ".join(report.location_ids.mapped("complete_name")) if report.location_ids else "All Internal/Transit Locations", text_format)
        worksheet.write(4, 0, "Product Categories", label_format)
        worksheet.write(4, 1, ", ".join(report.product_categ_ids.mapped("display_name")) if report.product_categ_ids else "All Categories", text_format)
        worksheet.write(5, 0, "Products", label_format)
        worksheet.write(5, 1, ", ".join(report.product_ids.mapped("display_name")) if report.product_ids else "All Products", text_format)

        headers = [
            "Location",
            "Product Category",
            "Product",
            "Date",
            "Transaction Reference",
            "Source Document",
            "Source Location",
            "Destination Location",
            "Qty",
            "In",
            "Out",
            "Balance",
            "UoM",
            "Picking",
            "Stock Move",
        ]
        row = 7
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, header_format)
        row += 1

        current_location = False
        current_category = False
        current_product = False
        for line in report.line_ids.sorted(
            key=lambda l: (
                l.location_id.complete_name or "",
                l.product_categ_id.complete_name or "",
                l.product_id.display_name or "",
                l.date or fields.Datetime.from_string("1900-01-01 00:00:00"),
                l.move_id.id or 0,
                l.id or 0,
            )
        ):
            if line.location_id != current_location:
                current_location = line.location_id
                current_category = False
                current_product = False
                worksheet.merge_range(row, 0, row, len(headers) - 1, "Location: %s" % (line.location_id.complete_name or line.location_id.display_name or ""), section_format)
                row += 1
            if line.product_categ_id != current_category:
                current_category = line.product_categ_id
                current_product = False
                worksheet.merge_range(row, 0, row, len(headers) - 1, "Category: %s" % (line.product_categ_id.complete_name or line.product_categ_id.display_name or ""), section_format)
                row += 1
            if line.product_id != current_product:
                current_product = line.product_id
                worksheet.merge_range(row, 0, row, len(headers) - 1, "Product: %s" % (line.product_id.display_name or ""), section_format)
                row += 1

            worksheet.write(row, 0, line.location_id.complete_name or line.location_id.display_name or "", text_format)
            worksheet.write(row, 1, line.product_categ_id.complete_name or line.product_categ_id.display_name or "", text_format)
            worksheet.write(row, 2, line.product_id.display_name or "", text_format)
            if line.date:
                worksheet.write_datetime(row, 3, line.date, date_format)
            else:
                worksheet.write(row, 3, "", text_format)
            worksheet.write(row, 4, line.reference or "", text_format)
            worksheet.write(row, 5, line.source_document or "", text_format)
            worksheet.write(row, 6, line.source_location_id.complete_name or "", text_format)
            worksheet.write(row, 7, line.dest_location_id.complete_name or "", text_format)
            worksheet.write_number(row, 8, line.product_qty or 0.0, number_format)
            worksheet.write_number(row, 9, line.product_in or 0.0, number_format)
            worksheet.write_number(row, 10, line.product_out or 0.0, number_format)
            worksheet.write_number(row, 11, line.balance or 0.0, number_format)
            worksheet.write(row, 12, line.product_uom.display_name or "", text_format)
            worksheet.write(row, 13, line.picking_id.display_name or "", text_format)
            worksheet.write(row, 14, line.move_id.display_name or "", text_format)
            row += 1

        worksheet.set_row(0, 24)
        worksheet.set_column(0, 2, 28)
        worksheet.set_column(3, 3, 18)
        worksheet.set_column(4, 7, 28)
        worksheet.set_column(8, 11, 14)
        worksheet.set_column(12, 14, 20)
        workbook.close()
        return output

    @http.route(
        "/stock_card_report/export_xlsx/<int:wizard_id>",
        type="http",
        auth="user",
    )
    def export_xlsx(self, wizard_id, **kwargs):
        if xlsxwriter is None:
            return request.not_found()

        wizard = request.env["stock.card.report.wizard"].browse(wizard_id).exists()
        if not wizard:
            return request.not_found()

        report = request.env["report.stock.card.report"].create(
            wizard._prepare_stock_card_report()
        )
        return self._xlsx_response(self._build_stock_card_xlsx(report), "stock_card_report.xlsx")

    @http.route(
        "/stock_card_report/export_xlsx_report/<int:report_id>",
        type="http",
        auth="user",
    )
    def export_xlsx_report(self, report_id, **kwargs):
        if xlsxwriter is None:
            return request.not_found()

        report = request.env["report.stock.card.report"].browse(report_id).exists()
        if not report:
            return request.not_found()
        return self._xlsx_response(self._build_stock_card_xlsx(report), "stock_card_report.xlsx")

    @http.route(
        "/stock_card_report/location_export_xlsx/<int:wizard_id>",
        type="http",
        auth="user",
    )
    def location_export_xlsx(self, wizard_id, **kwargs):
        if xlsxwriter is None:
            return request.not_found()

        wizard = request.env["stock.location.card.report.wizard"].browse(wizard_id).exists()
        if not wizard:
            return request.not_found()

        report = request.env["report.stock.location.card.report"].create(
            wizard._prepare_stock_location_card_report()
        )
        return self._xlsx_response(
            self._build_location_card_xlsx(report), "stock_location_card_report.xlsx"
        )

    @http.route(
        "/stock_card_report/location_export_xlsx_report/<int:report_id>",
        type="http",
        auth="user",
    )
    def location_export_xlsx_report(self, report_id, **kwargs):
        if xlsxwriter is None:
            return request.not_found()

        report = request.env["report.stock.location.card.report"].browse(report_id).exists()
        if not report:
            return request.not_found()
        return self._xlsx_response(
            self._build_location_card_xlsx(report), "stock_location_card_report.xlsx"
        )
