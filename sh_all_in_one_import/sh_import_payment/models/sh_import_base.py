# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_company(self):
        return self.env.company

    sh_import_payment_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    sh_import_payment_is_create_partner = fields.Boolean('Create Customer/Vendor ?')
    sh_import_payment_is_confirm_payment = fields.Boolean('Confirm/Posted Payment ?')
    sh_import_payment_partner_by = fields.Selection([('id', 'Database ID'), ('name', 'Name'), ('email', 'Email'), (
        'mobile', 'Mobile'), ('phone', 'Phone'), ('ref', 'Reference')], string='Partner By', default='name')
    sh_company_id_payment = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_payment_boolean = fields.Boolean(
        "Import Payments Boolean", compute="check_sh_import_payment")

    def check_sh_import_payment(self):
        if self.sh_technical_name == 'sh_import_payment':
            self.sh_import_payment_boolean = True
        else:
            self.sh_import_payment_boolean = False

    def import_payment_apply(self):
        self.write({
            'sh_import_payment_type': self.sh_import_payment_type,
            'sh_import_payment_is_create_partner':self.sh_import_payment_is_create_partner,
            'sh_import_payment_is_confirm_payment':self.sh_import_payment_is_confirm_payment,
            'sh_import_payment_partner_by':self.sh_import_payment_partner_by,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
