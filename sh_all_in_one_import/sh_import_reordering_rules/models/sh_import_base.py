# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_company(self):
        return self.env.company

    sh_import_reordering_rule_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)

    sh_import_reordering_rule_method = fields.Selection([
        ('create', 'Create New Reordering Rules'),
        ('update', 'Update Existing Reordering Rules')
    ], default="create", string="Method", required=True)

    sh_import_reordering_rule_product_by = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], default="name", string="Product By", required=True)

    sh_company_id_reordering_rule = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_reordering_rule_boolean = fields.Boolean(
        "Import Reordering Rule Boolean", compute="check_sh_import_reordering_rule")

    def check_sh_import_reordering_rule(self):
        if self.sh_technical_name == 'sh_import_reordering_rules':
            self.sh_import_reordering_rule_boolean = True
        else:
            self.sh_import_reordering_rule_boolean = False

    def import_reordering_rule_apply(self):
        self.write({
            'sh_import_reordering_rule_type': self.sh_import_reordering_rule_type,
            'sh_import_reordering_rule_method':self.sh_import_reordering_rule_method,
            'sh_import_reordering_rule_product_by':self.sh_import_reordering_rule_product_by,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
