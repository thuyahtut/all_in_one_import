# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api
from odoo.exceptions import UserError


class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def _default_schedule_date_int_transfer(self):
        return fields.Datetime.now()

    @api.model
    def _default_location_id_int_transfer(self):
        company_user = self.env.company
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', company_user.id)], limit=1)
        if warehouse:
            return warehouse.lot_stock_id.id
        else:
            raise UserError(
                _('You must define a warehouse for the company: %s.') % (company_user.name,))

    sh_import_int_transfer_scheduled_date = fields.Datetime(
        string="Scheduled Date", default=_default_schedule_date_int_transfer)
    sh_import_int_transfer_location_id = fields.Many2one(
        'stock.location', "Source Location",
        default=_default_location_id_int_transfer)

    sh_import_int_transfer_location_dest_id = fields.Many2one(
        'stock.location', "Destination Location",
        default=_default_location_id_int_transfer)

    sh_import_int_transfer_product_by = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], default="name", string="Product By")


    sh_import_int_transfer_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type")
    sh_import_int_transfer_boolean = fields.Boolean(
        "Import Internal Transfer Adv Boolean", compute="check_sh_import_int_transfer")

    def check_sh_import_int_transfer(self):
        if self.sh_technical_name == 'sh_import_int_transfer':
            self.sh_import_int_transfer_boolean = True
        else:
            self.sh_import_int_transfer_boolean = False

    def import_int_transfer_apply(self):
        self.write({
            'sh_import_int_transfer_scheduled_date': self.sh_import_int_transfer_scheduled_date,
            'sh_import_int_transfer_location_id':self.sh_import_int_transfer_location_id.id,
            'sh_import_int_transfer_location_dest_id':self.sh_import_int_transfer_location_dest_id.id,
            'sh_import_int_transfer_product_by':self.sh_import_int_transfer_product_by,
            'sh_import_int_transfer_type':self.sh_import_int_transfer_type,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
