# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_company(self):
        return self.env.company

    sh_import_prod_temp_import_type = fields.Selection([('csv', 'CSV File'),
                                    ('excel', 'Excel File')],
                                   default="csv",
                                   string="Import File Type",
                                   required=True)
    sh_import_prod_temp_method = fields.Selection([
        ('create', 'Create Product'),
        ('write', 'Create or Update Product')
    ], default="create", string="Method", required=True)

    sh_import_prod_temp_product_update_by = fields.Selection([
        ('barcode', 'Barcode'),
        ('int_ref', 'Internal Reference'),
    ], default='barcode', string="Product Update By", required=True)
    sh_company_id_product_temp = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_product_temp_boolean = fields.Boolean(
        "Import Product Template Boolean", compute="check_sh_import_product_temp")

    def check_sh_import_product_temp(self):
        if self.sh_technical_name == 'sh_import_product_tmpl':
            self.sh_import_product_temp_boolean = True
        else:
            self.sh_import_product_temp_boolean = False

    def import_product_temp_apply(self):
        self.write({
            'sh_import_prod_temp_import_type': self.sh_import_prod_temp_import_type,
            'sh_import_prod_temp_product_update_by': self.sh_import_prod_temp_product_update_by,
            'sh_import_prod_temp_method': self.sh_import_prod_temp_method,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
