# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    import_emp_img_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type")
    emp_by = fields.Selection([
        ('name', 'Name'),
        ('db_id', 'ID'),
        ('id_no', 'Identification No')
    ], default="name", string="Employee By")
    sh_import_emp_img_boolean = fields.Boolean(
        "Import Emp Img Boolean", compute="check_sh_import_emp_img")

    def check_sh_import_emp_img(self):
        if self.sh_technical_name == 'sh_import_emp_img':
            self.sh_import_emp_img_boolean = True
        else:
            self.sh_import_emp_img_boolean = False

    def import_emp_img_apply(self):
        self.write({
            'import_emp_img_type': self.import_emp_img_type,
            'emp_by': self.emp_by,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
