# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_company(self):
        return self.env.company

    sh_import_users_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    sh_import_users_group_import_type = fields.Selection(
        [('id', 'Id'), ('name', 'Name')], default='id',string='Group Import Type')
    sh_company_id_users = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_users_boolean = fields.Boolean(
        "Import Users Boolean", compute="check_sh_import_users")

    def check_sh_import_users(self):
        if self.sh_technical_name == 'sh_import_users':
            self.sh_import_users_boolean = True
        else:
            self.sh_import_users_boolean = False

    def import_users_apply(self):
        self.write({
            'sh_import_users_type': self.sh_import_users_type,
            'sh_import_users_group_import_type': self.sh_import_users_group_import_type,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
