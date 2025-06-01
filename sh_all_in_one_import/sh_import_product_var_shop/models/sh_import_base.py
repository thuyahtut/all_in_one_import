# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_company(self):
        return self.env.company

    sh_import_product_var_shop_type = fields.Selection([('csv', 'CSV File'),
                                    ('excel', 'Excel File')],
                                   default="csv",
                                   string="Import File Type",
                                   required=True)
    sh_import_product_var_shop_method = fields.Selection([('create', 'Create Product Variants'),
                               ('write', 'Create or Update Product Variants')],
                              default="create",
                              string="Method",
                              required=True)

    sh_import_product_var_shop_product_update_by = fields.Selection([
        ('name', 'Name'),
        ('barcode', 'Barcode'),
        ('int_ref', 'Internal Reference'),
    ],default='name',string="Product Variant Update By",required=True)

    sh_import_product_var_shop_is_create_m2m_record = fields.Boolean(
        string="Create a New Record for Dynamic M2M Field (if not exist)?")

    sh_import_product_var_shop_is_create_categ_id_record = fields.Boolean(
        string="Create a New Record for Product Category Field (if not exist)?"
    )
    sh_company_id_product_var_shop = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_product_var_shop_boolean = fields.Boolean(
        "Import Variant Shop Boolean", compute="check_sh_import_product_var_shop")

    def check_sh_import_product_var_shop(self):
        if self.sh_technical_name == 'sh_import_product_var_shop':
            self.sh_import_product_var_shop_boolean = True
        else:
            self.sh_import_product_var_shop_boolean = False

    def import_product_var_shop_apply(self):
        self.write({
            'sh_import_product_var_shop_type': self.sh_import_product_var_shop_type,
            'sh_import_product_var_shop_product_update_by': self.sh_import_product_var_shop_product_update_by,
            'sh_import_product_var_shop_is_create_m2m_record': self.sh_import_product_var_shop_is_create_m2m_record,
            'sh_import_product_var_shop_is_create_categ_id_record':self.sh_import_product_var_shop_is_create_categ_id_record,
            'sh_import_product_var_shop_method': self.sh_import_product_var_shop_method,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
