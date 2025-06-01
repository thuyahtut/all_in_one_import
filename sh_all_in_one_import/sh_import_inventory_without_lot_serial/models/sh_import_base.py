# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api
from odoo.exceptions import UserError

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def _default_location_id(self):
        company_user = self.env.company
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', company_user.id)], limit=1)
        if warehouse:
            return warehouse.lot_stock_id.id
        else:
            raise UserError(
                _('You must define a warehouse for the company: %s.') % (company_user.name,))

    @api.model
    def default_company(self):
        return self.env.company

    sh_import_without_lot_serial_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type")

    sh_import_without_lot_serial_product_by = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], default="name", string="Product By")

    sh_import_without_lot_serial_location_id = fields.Many2one("stock.location", string="Location",
                                  domain="[('usage','not in', ['supplier','production'])]", default=_default_location_id)
    sh_import_without_lot_serial_name = fields.Char(string="Inventory Reference")
    sh_company_id_without_lot_serial = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_without_lot_serial_boolean = fields.Boolean(
        "Import Lead Boolean", compute="check_sh_import_without_lot_serial")

    def check_sh_import_without_lot_serial(self):
        if self.sh_technical_name == 'sh_import_inventory_without_lot_serial':
            self.sh_import_without_lot_serial_boolean = True
        else:
            self.sh_import_without_lot_serial_boolean = False

    def import_without_lot_serial_apply(self):
        self.write({
            'sh_import_without_lot_serial_type': self.sh_import_without_lot_serial_type,
            'sh_import_without_lot_serial_product_by':self.sh_import_without_lot_serial_product_by,
            'sh_import_without_lot_serial_location_id':self.sh_import_without_lot_serial_location_id.id,
            'sh_import_without_lot_serial_name':self.sh_import_without_lot_serial_name,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
