# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models,_,api
from odoo.exceptions import UserError

class DefaultProductImage(models.Model):
    _inherit = "sh.import.base"
    
    import_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    product_by = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], default="name", string="Product By", required=True)
    product_model = fields.Selection([
        ('pro_var', 'Product Variants'),
        ('pro_tmpl', 'Product Template')
    ], default="pro_var", string="Product Model", required=True)
    sh_import_product_img_boolean = fields.Boolean("Product Image Boolean",compute="check_sh_import_product_img")

    def check_sh_import_product_img(self):
        if self.sh_technical_name == 'sh_import_product_img':
            self.sh_import_product_img_boolean = True
        else:
            self.sh_import_product_img_boolean = False
    
    def import_product_img_apply(self):
        self.write({
            'import_type' : self.import_type,
            'product_by' : self.product_by,
            'product_model' : self.product_model,
            'on_error' : self.on_error,
            'import_limit' : self.import_limit
        })