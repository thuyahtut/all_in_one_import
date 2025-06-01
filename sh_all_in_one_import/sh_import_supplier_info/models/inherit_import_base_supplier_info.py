# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class DefaultSupplierInfo(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_company(self):
        return self.env.company

    sh_import_type_supplier = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File'),
    ], default="csv", string=" Import File Type  ", required=True)
    sh_product_model_supplier = fields.Selection([
        ('pro_var', 'Product Variants'),
        ('pro_tmpl', 'Product Template')
    ], default="pro_var", string="  Product Model ", required=True)

    sh_product_by_supplier = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], default="name", string="Product By ")
    sh_method_supplier = fields.Selection(
        [('create', "Create Supplier Info"), ('update', 'Create or Update Supplier Info')], default="create", string="Method")
    sh_company_id_supplier = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_supplier_info_boolean = fields.Boolean(
        "Supplier Info Boolean", compute="check_sh_supplier_info")

    def check_sh_supplier_info(self):
        if self.sh_technical_name == 'sh_import_supplier_info':
            self.sh_import_supplier_info_boolean = True
        else:
            self.sh_import_supplier_info_boolean = False

    def import_supplier_info_apply(self):
        self.write({
            'sh_import_type_supplier': self.sh_import_type_supplier,
            'sh_product_by_supplier': self.sh_product_by_supplier,
            'sh_product_model_supplier': self.sh_product_model_supplier,
            'sh_method_supplier': self.sh_method_supplier,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
