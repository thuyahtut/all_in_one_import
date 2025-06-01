# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_company(self):
        return self.env.company

    sh_import_lead_file_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    sh_import_lead_type = fields.Selection(
        [('lead', 'Lead'), ('opportunity', 'Opportunity')], default='lead', string="Import Type")
    sh_company_id_lead = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_lead_boolean = fields.Boolean(
        "Import Lead Boolean", compute="check_sh_import_lead")

    def check_sh_import_lead(self):
        if self.sh_technical_name == 'sh_import_lead':
            self.sh_import_lead_boolean = True
        else:
            self.sh_import_lead_boolean = False

    def import_lead_apply(self):
        self.write({
            'sh_import_lead_file_type': self.sh_import_lead_file_type,
            'sh_import_lead_type':self.sh_import_lead_type,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
