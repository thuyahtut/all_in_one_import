# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_company(self):
        return self.env.company

    sh_import_partner_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    sh_import_partner_is_customer = fields.Boolean(string="Is a Customer", default=True)
    sh_import_partner_is_supplier = fields.Boolean(string="Is a Vendor")
    sh_import_partner_method = fields.Selection([
        ('create', 'Create Customer/Vendor'),
        ('write', 'Create or Update Customer/Vendor')
    ], default="create", string="Method", required=True)
    sh_import_partner_contact_update_by = fields.Selection([
        ('name', 'Name'),
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('mobile', 'Mobile'),
        ('ref', 'Reference'),
        ('id', 'ID'),
    ], default='name', string="Customer/Vendor Update By", required=True)
    sh_company_id_partner = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_partner_boolean = fields.Boolean(
        "Import Partner Boolean", compute="check_sh_import_partner")

    def check_sh_import_partner(self):
        if self.sh_technical_name == 'sh_import_partner':
            self.sh_import_partner_boolean = True
        else:
            self.sh_import_partner_boolean = False

    def import_partner_apply(self):
        self.write({
            'sh_import_partner_type': self.sh_import_partner_type,
            'sh_import_partner_is_customer':self.sh_import_partner_is_customer,
            'sh_import_partner_is_supplier':self.sh_import_partner_is_supplier,
            'sh_import_partner_method':self.sh_import_partner_method,
            'sh_import_partner_contact_update_by':self.sh_import_partner_contact_update_by,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
