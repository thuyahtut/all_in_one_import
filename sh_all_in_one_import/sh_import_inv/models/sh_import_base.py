# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api
from odoo.exceptions import UserError

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_inv_company(self):
        return self.env.company

    sh_import_inv_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type")
    sh_import_inv_product_by = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], default="name", string="Product By")
    sh_import_inv_invoice_type = fields.Selection([
        ('inv', 'Customer Invoice'),
        ('bill', 'Vendor Bill'),
        ('ccn', 'Customer Credit Note'),
        ('vcn', 'Vendor Credit Note')
    ], default="inv", string="Invoicing Type")
    sh_import_inv_is_validate = fields.Boolean(string="Auto Post?")
    sh_import_inv_inv_no_type = fields.Selection([
        ('auto', 'Auto'),
        ('as_per_sheet', 'As per sheet')
    ], default="auto", string="Number")
    sh_import_inv_account_option = fields.Selection(
        [('default', 'Auto'), ('sheet', 'As per sheet')], default='default', string='Account')
    sh_import_inv_partner_by = fields.Selection([
        ('name', 'Name'),
        ('ref', 'Reference'),
        ('id', 'ID')
    ], default="name", string="Customer By")
    sh_company_id_inv= fields.Many2one(
        'res.company', string='Company', default=default_inv_company, required=True)
    sh_import_inv_boolean = fields.Boolean(
        "Import Invoice Boolean", compute="check_sh_import_inv")

    def check_sh_import_inv(self):
        if self.sh_technical_name == 'sh_import_inv':
            self.sh_import_inv_boolean = True
        else:
            self.sh_import_inv_boolean = False

    def import_inv_apply(self):
        self.write({
            'sh_import_inv_type': self.sh_import_inv_type,
            'sh_import_inv_product_by':self.sh_import_inv_product_by,
            'sh_import_inv_invoice_type':self.sh_import_inv_invoice_type,
            'sh_import_inv_is_validate':self.sh_import_inv_is_validate,
            'sh_import_inv_inv_no_type':self.sh_import_inv_inv_no_type,
            'sh_import_inv_account_option':self.sh_import_inv_account_option,
            'sh_import_inv_partner_by':self.sh_import_inv_partner_by,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
