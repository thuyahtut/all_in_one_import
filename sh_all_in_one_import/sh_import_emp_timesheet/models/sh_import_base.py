# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    import_emp_timesheet_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type")
    sh_import_emp_timesheet_boolean = fields.Boolean(
        "Import Emp Timesheet Boolean", compute="check_sh_import_emp_timesheet")

    def check_sh_import_emp_timesheet(self):
        if self.sh_technical_name == 'sh_import_emp_timesheet':
            self.sh_import_emp_timesheet_boolean = True
        else:
            self.sh_import_emp_timesheet_boolean = False

    def import_emp_timesheet_apply(self):
        self.write({
            'import_emp_timesheet_type': self.import_emp_timesheet_type,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
