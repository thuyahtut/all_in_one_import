# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    import_attendance_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type ")
    attendance_by = fields.Selection([('employee_id', 'Employee ID'), (
        'badge', 'Badge')], default="employee_id", string="Attendance Import Type")
    sh_import_attendance_boolean = fields.Boolean(
        "Import Attendance Boolean", compute="check_sh_import_attendance")

    def check_sh_import_attendance(self):
        if self.sh_technical_name == 'sh_import_attendance':
            self.sh_import_attendance_boolean = True
        else:
            self.sh_import_attendance_boolean = False

    def import_attendance_apply(self):
        self.write({
            'import_attendance_type': self.import_attendance_type,
            'attendance_by':self.attendance_by,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
