# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api
from odoo.exceptions import UserError

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_inv_with_payment_company(self):
        return self.env.company

    sh_import_inv_with_payment_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type")
    sh_import_inv_with_payment_product_by = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], default="name", string="Product By")
    sh_import_inv_with_payment_invoice_type = fields.Selection([
        ('inv', 'Customer Invoice'),
        ('bill', 'Vendor Bill'),
        ('ccn', 'Customer Credit Note'),
        ('vcn', 'Vendor Credit Note')
    ], default="inv", string="Invoicing Type")
    sh_import_inv_with_payment_is_validate = fields.Boolean(string="Auto Post?")
    sh_import_inv_with_payment_is_payment = fields.Boolean(string="Auto Payment?")
    sh_import_inv_with_payment_payment_option = fields.Selection([('partial', 'Invoice Keep Open'), (
        'write_off', 'Write Off')], default='partial', string="Payment Type")
    sh_import_inv_with_payment_write_off_account_id = fields.Many2one(
        'account.account', string='Post Difference In')
    sh_import_inv_with_payment_account_option = fields.Selection(
        [('default', 'Auto'), ('sheet', 'As per sheet')], default='default', string="Account")

    sh_import_inv_with_payment_inv_no_type = fields.Selection([
        ('auto', 'Auto'),
        ('as_per_sheet', 'As per sheet')
    ], default="auto", string="Number", required=True)

    sh_import_inv_with_payment_partner_by = fields.Selection([
        ('name', 'Name'),
        ('ref', 'Reference'),
        ('id', 'ID')
    ], default="name", string="Customer By")
    sh_company_id_inv_with_payment = fields.Many2one(
        'res.company', string='Company', default=default_inv_with_payment_company, required=True)
    sh_import_inv_with_payment_boolean = fields.Boolean(
        "Import Invoice With Payment Boolean", compute="check_sh_import_inv_with_payment")

    @api.onchange('sh_import_inv_with_payment_is_validate')
    def _onchange_is_validate(self):
        if not self.sh_import_inv_with_payment_is_validate:
            self.sh_import_inv_with_payment_is_payment = False

    def check_sh_import_inv_with_payment(self):
        if self.sh_technical_name == 'sh_import_inv_with_payment':
            self.sh_import_inv_with_payment_boolean = True
        else:
            self.sh_import_inv_with_payment_boolean = False

    def import_inv_with_payment_apply(self):
        self.write({
            'sh_import_inv_with_payment_type': self.sh_import_inv_with_payment_type,
            'sh_import_inv_with_payment_product_by':self.sh_import_inv_with_payment_product_by,
            'sh_import_inv_with_payment_invoice_type':self.sh_import_inv_with_payment_invoice_type,
            'sh_import_inv_with_payment_is_validate':self.sh_import_inv_with_payment_is_validate,
            'sh_import_inv_with_payment_is_payment':self.sh_import_inv_with_payment_is_payment,
            'sh_import_inv_with_payment_payment_option':self.sh_import_inv_with_payment_payment_option,
            'sh_import_inv_with_payment_write_off_account_id':self.sh_import_inv_with_payment_write_off_account_id.id,
            'sh_import_inv_with_payment_account_option':self.sh_import_inv_with_payment_account_option,
            'sh_import_inv_with_payment_inv_no_type':self.sh_import_inv_with_payment_inv_no_type,
            'sh_import_inv_with_payment_partner_by':self.sh_import_inv_with_payment_partner_by,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
