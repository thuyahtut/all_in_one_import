# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_company(self):
        return self.env.company

    sh_import_entry_accounting_date = fields.Date('Accounting Date')
    sh_import_entry_journal_id = fields.Many2one(
        'account.journal', 'Journal')
    sh_import_entry_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)

    sh_import_entry_partner_by = fields.Selection([
        ('name', 'Name'),
        ('ref', 'Reference'),
        ('id', 'ID')
    ], default="name", string="Customer By")

    sh_company_id_journal_entry = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_journal_entry_boolean = fields.Boolean(
        "Import Journal Entry Boolean", compute="check_sh_import_journal_entry")

    def check_sh_import_journal_entry(self):
        if self.sh_technical_name == 'sh_import_journal_entry':
            self.sh_import_journal_entry_boolean = True
        else:
            self.sh_import_journal_entry_boolean = False

    def import_journal_entry_apply(self):
        self.write({
            'sh_import_entry_accounting_date': self.sh_import_entry_accounting_date,
            'sh_import_entry_journal_id':self.sh_import_entry_journal_id.id,
            'sh_import_entry_type':self.sh_import_entry_type,
            'sh_import_entry_partner_by':self.sh_import_entry_partner_by,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
