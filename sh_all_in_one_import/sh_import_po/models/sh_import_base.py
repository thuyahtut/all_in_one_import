# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_company(self):
        return self.env.company

    sh_import_po_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    sh_import_po_product_by = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], default="name", string="Product By", required=True)
    sh_import_po_is_create_vendor = fields.Boolean(string="Create Vendor?")
    sh_import_po_is_confirm_order = fields.Boolean(string="Auto Confirm Order?")
    sh_import_po_order_no_type = fields.Selection([
        ('auto', 'Auto'),
        ('as_per_sheet', 'As per sheet')
    ], default="auto", string="Reference Number", required=True)
    sh_import_po_unit_price = fields.Selection([
        ('sheet', 'Based on Sheet'),
        ('pricelist', 'Based on Pricelist'),
    ], default="sheet", string="Unit Price", required=True)
    sh_import_po_partner_by = fields.Selection([
        ('name', 'Name'),
        ('ref', 'Reference'),
        ('id', 'ID')
    ], default="name", string="Vendor By")
    sh_company_id_po = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_po_boolean = fields.Boolean(
        "Import POS Order Boolean", compute="check_sh_import_po")

    def check_sh_import_po(self):
        if self.sh_technical_name == 'sh_import_po':
            self.sh_import_po_boolean = True
        else:
            self.sh_import_po_boolean = False

    def import_po_apply(self):
        self.write({
            'sh_import_po_type': self.sh_import_po_type,
            'sh_import_po_product_by':self.sh_import_po_product_by,
            'sh_import_po_is_create_vendor':self.sh_import_po_is_create_vendor,
            'sh_import_po_is_confirm_order':self.sh_import_po_is_confirm_order,
            'sh_import_po_order_no_type':self.sh_import_po_order_no_type,
            'sh_import_po_unit_price':self.sh_import_po_unit_price,
            'sh_import_po_partner_by':self.sh_import_po_partner_by,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
