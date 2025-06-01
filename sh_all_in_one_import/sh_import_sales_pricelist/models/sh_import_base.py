# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_company(self):
        return self.env.company

    sh_import_sale_pricelist_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    sh_import_sale_pricelist_by = fields.Selection([
        ('add', 'Add Sales Pricelist'),
        ('update', 'Update Sales Pricelist')
    ], default="add", string="Import Pricelist By", required=True)

    sh_import_sale_pricelist_product_by = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], string="Product By", default='name')
    sh_import_sale_pricelist_applied_on = fields.Selection([
        ('2_product_category', 'Product Category'),
        ('1_product', 'Product'),
        ('0_product_variant', 'Product Variant')
    ], default='1_product', string="Applied On")
    sh_import_sale_pricelist_compute_price = fields.Selection([
        ('fixed', 'Fixed Price'),
        ('percentage', 'Percentage (discount)'),
        ('formula', 'Formula')
    ], string="Compute Price", default='fixed')
    sh_import_sale_pricelist_country_group_ids = fields.Many2many(
        'res.country.group', string="Country Groups")
    sh_import_sale_pricelist_base = fields.Selection([
        ('list_price', 'Sales Price'),
        ('standard_price', 'Cost'),
        ('pricelist', 'Other Pricelist')
    ], string='Based On', default='list_price')

    sh_company_id_sale_pricelist = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_sale_pricelist_boolean = fields.Boolean(
        "Import Sale Pricelist Boolean", compute="check_sh_import_sale_pricelist")

    def check_sh_import_sale_pricelist(self):
        if self.sh_technical_name == 'sh_import_sales_pricelist':
            self.sh_import_sale_pricelist_boolean = True
        else:
            self.sh_import_sale_pricelist_boolean = False

    def import_sale_pricelist_apply(self):
        self.write({
            'sh_import_sale_pricelist_type': self.sh_import_sale_pricelist_type,
            'sh_import_sale_pricelist_by':self.sh_import_sale_pricelist_by,
            'sh_import_sale_pricelist_product_by':self.sh_import_sale_pricelist_product_by,
            'sh_import_sale_pricelist_applied_on':self.sh_import_sale_pricelist_applied_on,
            'sh_import_sale_pricelist_compute_price':self.sh_import_sale_pricelist_compute_price,
            'sh_import_sale_pricelist_country_group_ids':[(6,0,self.sh_import_sale_pricelist_country_group_ids.ids)],
            'sh_import_sale_pricelist_base':self.sh_import_sale_pricelist_base,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
