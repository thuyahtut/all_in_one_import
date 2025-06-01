# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_company_expense(self):
        return self.env.company

    sh_import_expense_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type")
    sh_expense_type = fields.Selection(
        [('expense', 'Expense'), ('expense_sheet', 'Expense Sheet')], string="Import", default="expense")
    sh_employee_type = fields.Selection([('name', 'Name'), ('work_phone', 'Work Phone'), (
        'work_email', 'Work Email'), ('badge_id', 'Badge ID')], string="Employee By", default="name")
    sh_import_expense_product_type = fields.Selection([('name', 'Name'), ('internal_ref', 'Internal Refrence'), (
        'barcode', 'Barcode')], string="Product By", default="name")
    sh_import_expense_boolean = fields.Boolean(
        "Import Expense Boolean", compute="check_sh_import_expense")

    def check_sh_import_expense(self):
        if self.sh_technical_name == 'sh_import_expense':
            self.sh_import_expense_boolean = True
        else:
            self.sh_import_expense_boolean = False

    def import_expense_apply(self):
        self.write({
            'sh_import_expense_type': self.sh_import_expense_type,
            'sh_expense_type':self.sh_expense_type,
            'sh_employee_type':self.sh_employee_type,
            'sh_import_expense_product_type':self.sh_import_expense_product_type,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
