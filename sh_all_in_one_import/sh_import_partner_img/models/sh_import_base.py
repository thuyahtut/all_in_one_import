# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_company(self):
        return self.env.company

    sh_import_partner_img_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    sh_import_partner_img_partner_by = fields.Selection([
        ('name', 'Name'),
        ('db_id', 'ID')
    ], default="name", string="Customer By", required=True)
    sh_company_id_partner_img = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_partner_img_boolean = fields.Boolean(
        "Import Partner Image Boolean", compute="check_sh_import_partner_img")

    def check_sh_import_partner_img(self):
        if self.sh_technical_name == 'sh_import_partner_img':
            self.sh_import_partner_img_boolean = True
        else:
            self.sh_import_partner_img_boolean = False

    def import_partner_img_apply(self):
        self.write({
            'sh_import_partner_img_type': self.sh_import_partner_img_type,
            'sh_import_partner_img_partner_by':self.sh_import_partner_img_partner_by,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
