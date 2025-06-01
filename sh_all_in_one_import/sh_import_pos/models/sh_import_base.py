# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_company(self):
        return self.env.company

    sh_import_pos_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    sh_import_pos_product_by = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], default="name", string="Product By", required=True)
    sh_import_pos_is_create_customer = fields.Boolean(string="Create Customer?")
    sh_import_pos_order_no_type = fields.Selection([
        ('auto', 'Auto'),
        ('as_per_sheet', 'As per sheet')
    ], default="auto", string="POS Order Number", required=True)
    sh_import_pos_partner_by = fields.Selection([
        ('name', 'Name'),
        ('ref', 'Reference'),
        ('id', 'ID')
    ], default="name", string="Customer By")
    sh_company_id_pos = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_pos_boolean = fields.Boolean(
        "Import POS Order Boolean", compute="check_sh_import_pos")

    def check_sh_import_pos(self):
        if self.sh_technical_name == 'sh_import_pos':
            self.sh_import_pos_boolean = True
        else:
            self.sh_import_pos_boolean = False

    def import_pos_apply(self):
        self.write({
            'sh_import_pos_type': self.sh_import_pos_type,
            'sh_import_pos_product_by':self.sh_import_pos_product_by,
            'sh_import_pos_is_create_customer':self.sh_import_pos_is_create_customer,
            'sh_import_pos_order_no_type':self.sh_import_pos_order_no_type,
            'sh_import_pos_partner_by':self.sh_import_pos_partner_by,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
