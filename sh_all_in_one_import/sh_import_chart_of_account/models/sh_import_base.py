# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    import_coa_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type")
    sh_import_coa_boolean = fields.Boolean(
        "Import COA Boolean", compute="check_sh_import_coa")

    def check_sh_import_coa(self):
        if self.sh_technical_name == 'sh_import_chart_of_account':
            self.sh_import_coa_boolean = True
        else:
            self.sh_import_coa_boolean = False

    def import_coa_apply(self):
        self.write({
            'import_coa_type': self.import_coa_type,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
