# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_company(self):
        return self.env.company

    import_type = fields.Selection([('csv', 'CSV File'),
                                    ('excel', 'Excel File')],
                                   default="csv",
                                   string="Import File Type",
                                   required=True)
    method = fields.Selection([('create', 'Create Product Variants'),
                               ('write', 'Create or Update Product Variants')],
                              default="create",
                              string="Method",
                              required=True)

    product_update_by = fields.Selection([
        ('name', 'Name'),
        ('barcode', 'Barcode'),
        ('int_ref', 'Internal Reference'),
    ],
                                         default='name',
                                         string="Product Variant Update By",
                                         required=True)

    is_create_m2m_record = fields.Boolean(
        string="Create a New Record for Dynamic M2M Field (if not exist)?")

    is_create_categ_id_record = fields.Boolean(
        string="Create a New Record for Product Category Field (if not exist)?"
    )
    sh_company_id_product_var = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_product_var_boolean = fields.Boolean(
        "Import Variant Boolean", compute="check_sh_import_product_var")

    def check_sh_import_product_var(self):
        if self.sh_technical_name == 'sh_import_product_var':
            self.sh_import_product_var_boolean = True
        else:
            self.sh_import_product_var_boolean = False

    def import_product_var_apply(self):
        self.write({
            'import_type': self.import_type,
            'product_update_by': self.product_update_by,
            'is_create_m2m_record': self.is_create_m2m_record,
            'is_create_categ_id_record':self.is_create_categ_id_record,
            'method': self.method,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
