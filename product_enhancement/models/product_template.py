from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    arabic_name = fields.Char(
        string='Arabic Name',
        copy=False,
        help='Arabic product name. This value is synchronized with the standard Arabic translation of Product Name.',
    )

    @api.model
    def _get_arabic_lang_code(self):
        """Return the active Arabic language code used for product translations."""
        language = self.env['res.lang'].search(
            [('active', '=', True), ('code', '=', 'ar_001')],
            limit=1,
        )
        if not language:
            language = self.env['res.lang'].search(
                [('active', '=', True), ('code', '=like', 'ar_%')],
                order='code',
                limit=1,
            )
        return language.code if language else False

    def _sync_arabic_name_to_translation(self):
        """Write Arabic Name into Odoo's native translation of product.name."""
        arabic_lang = self._get_arabic_lang_code()
        if not arabic_lang:
            return

        for product in self:
            product.with_context(
                lang=arabic_lang,
                skip_arabic_name_sync=True,
            ).write({'name': product.arabic_name or ''})

    def _sync_translation_to_arabic_name(self):
        """Keep Arabic Name aligned when Product Name is edited in Arabic UI."""
        current_lang = self.env.context.get('lang') or self.env.lang
        if not current_lang or not current_lang.startswith('ar'):
            return

        for product in self:
            product.with_context(skip_arabic_name_sync=True).write({
                'arabic_name': product.name or False,
            })

    @api.model_create_multi
    def create(self, vals_list):
        products = super().create(vals_list)
        if self.env.context.get('skip_arabic_name_sync'):
            return products

        for product, vals in zip(products, vals_list):
            if 'arabic_name' in vals:
                product._sync_arabic_name_to_translation()
            elif 'name' in vals:
                product._sync_translation_to_arabic_name()
        return products

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get('skip_arabic_name_sync'):
            return result

        if 'arabic_name' in vals:
            self._sync_arabic_name_to_translation()
        elif 'name' in vals:
            self._sync_translation_to_arabic_name()

        return result
