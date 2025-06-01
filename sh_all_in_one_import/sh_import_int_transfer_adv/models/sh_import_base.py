# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api
from odoo.exceptions import UserError


class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def _default_schedule_date(self):
        return fields.Datetime.now()

    @api.model
    def default_company(self):
        return self.env.company

    sh_import_int_transfer_adv_scheduled_date = fields.Datetime(
        string="Scheduled Date", default=_default_schedule_date)
    sh_import_int_transfer_adv_product_by = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], default="name", string="Product By")
    sh_import_int_transfer_adv_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type")
    sh_company_id_int_transfer_adv = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_int_transfer_adv_boolean = fields.Boolean(
        "Import Internal Transfer Adv Boolean", compute="check_sh_import_int_transfer_adv")

    def check_sh_import_int_transfer_adv(self):
        if self.sh_technical_name == 'sh_import_int_transfer_adv':
            self.sh_import_int_transfer_adv_boolean = True
        else:
            self.sh_import_int_transfer_adv_boolean = False

    def import_int_transfer_adv_apply(self):
        self.write({
            'sh_import_int_transfer_adv_scheduled_date': self.sh_import_int_transfer_adv_scheduled_date,
            'sh_import_int_transfer_adv_product_by':self.sh_import_int_transfer_adv_product_by,
            'sh_import_int_transfer_adv_type':self.sh_import_int_transfer_adv_type,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
