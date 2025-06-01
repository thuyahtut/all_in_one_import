# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def action_import_lot_serial(self):
        if self:
            action = self.env.ref(
                'sh_all_in_one_import.sh_import_lot_serial_action').read()[0]
            return action
