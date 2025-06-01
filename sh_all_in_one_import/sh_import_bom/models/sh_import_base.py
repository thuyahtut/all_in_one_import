# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    import_bom_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type  ")
    bom_type = fields.Selection([
        ('mtp', 'Manufacture this product'),
        ('kit', 'Kit')
    ], default="mtp", string="BoM Type")

    sh_import_bom_product_by = fields.Selection([
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], default="int_ref", string="Product Variant By ")
    sh_import_bom_product_template_by = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], default="name", string="Product By ")
    sh_import_bom_boolean = fields.Boolean(
        "Import BOM Boolean", compute="check_sh_import_bom")

    def check_sh_import_bom(self):
        if self.sh_technical_name == 'sh_import_bom':
            self.sh_import_bom_boolean = True
        else:
            self.sh_import_bom_boolean = False

    def import_bom_apply(self):
        self.write({
            'import_bom_type': self.import_bom_type,
            'bom_type':self.bom_type,
            'sh_import_bom_product_by':self.sh_import_bom_product_by,
            'sh_import_bom_product_template_by':self.sh_import_bom_product_template_by,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
