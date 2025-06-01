# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_company(self):
        return self.env.company

    sh_import_so_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    sh_import_so_product_by = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], default="name", string="Product By", required=True)
    sh_import_so_is_create_customer = fields.Boolean(string="Create Customer?")
    sh_import_so_is_confirm_sale = fields.Boolean(string="Auto Confirm Sale?")
    sh_import_so_order_no_type = fields.Selection([
        ('auto', 'Auto'),
        ('as_per_sheet', 'As per sheet')
    ], default="auto", string="Quotation/Order Number", required=True)
    sh_import_so_unit_price = fields.Selection([
        ('sheet', 'Based on Sheet'),
        ('pricelist', 'Based on Pricelist'),
    ], default="sheet", string="Unit Price", required=True)
    sh_import_so_partner_by = fields.Selection([
        ('name', 'Name'),
        ('ref', 'Reference'),
        ('id', 'ID')
    ], default="name", string="Customer By")
    sh_company_id_so = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_so_boolean = fields.Boolean(
        "Import Sale Order Boolean", compute="check_sh_import_so")

    def check_sh_import_so(self):
        if self.sh_technical_name == 'sh_import_so':
            self.sh_import_so_boolean = True
        else:
            self.sh_import_so_boolean = False

    def import_so_apply(self):
        self.write({
            'sh_import_so_type': self.sh_import_so_type,
            'sh_import_so_product_by':self.sh_import_so_product_by,
            'sh_import_so_is_create_customer':self.sh_import_so_is_create_customer,
            'sh_import_so_is_confirm_sale':self.sh_import_so_is_confirm_sale,
            'sh_import_so_order_no_type':self.sh_import_so_order_no_type,
            'sh_import_so_unit_price':self.sh_import_so_unit_price,
            'sh_import_so_partner_by':self.sh_import_so_partner_by,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
