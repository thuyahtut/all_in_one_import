# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, api, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
import pytz
from odoo.tools import ustr
import logging
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
_logger = logging.getLogger(__name__)


class Product(models.Model):
    _inherit = 'product.product'

    sh_display_name = fields.Char(
        'Compleate Name', related='display_name', search='_search_sh_display_name')

    def _search_sh_display_name(self, operator, value):
        product_ids = []
        for rec in self.search([]):
            if rec.sh_display_name and rec.sh_display_name == value:
                product_ids.append(rec.id)
        if operator == '=':
            return [('id', 'in', product_ids)]
        else:
            return []


class ImportPricelistWizard(models.TransientModel):
    _name = "sh.import.sale.pricelist"
    _description = "Import Pricelist wizard"

    @api.model
    def get_deafult_company(self):
        company_id = self.env.company
        return company_id

    import_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    import_by = fields.Selection([
        ('add', 'Add Sales Pricelist'),
        ('update', 'Update Sales Pricelist')
    ], default="add", string="Import Pricelist By", required=True)

    product_by = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], string="Product By", default='name')
    sh_applied_on = fields.Selection([
        ('2_product_category', 'Product Category'),
        ('1_product', 'Product'),
        ('0_product_variant', 'Product Variant')
    ], default='1_product', string="Applied On")
    sh_compute_price = fields.Selection([
        ('fixed', 'Fixed Price'),
        ('percentage', 'Percentage (discount)'),
        ('formula', 'Formula')
    ], string="Compute Price", default='fixed')
    sh_country_group_ids = fields.Many2many(
        'res.country.group', string="Country Groups")
    sh_base = fields.Selection([
        ('list_price', 'Sales Price'),
        ('standard_price', 'Cost'),
        ('pricelist', 'Other Pricelist')
    ], string='Based On', default='list_price')
    file = fields.Binary(string="File", required=True)
    company_id = fields.Many2one(
        'res.company', 'Company', default=get_deafult_company, required=True)

    def show_success_msg(self, counter, skipped_line_no):
        # open the new success message box
        view = self.env.ref('sh_message.sh_message_wizard')
        context = dict(self._context or {})
        dic_msg = str(counter) + " Records imported successfully"
        if skipped_line_no:
            dic_msg = dic_msg + "\nNote:"
        for k, v in skipped_line_no.items():
            dic_msg = dic_msg + "\nRow No " + k + " " + v + " "
        context['message'] = dic_msg

        return {
            'name': 'Success',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'sh.message.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    def read_xls_book(self):
        book = xlrd.open_workbook(file_contents=base64.decodebytes(self.file))
        sheet = book.sheet_by_index(0)
        # emulate Sheet.get_rows for pre-0.9.4
        values_sheet = []
        for rowx, row in enumerate(map(sheet.row, range(sheet.nrows)), 1):
            values = []
            for colx, cell in enumerate(row, 1):
                if cell.ctype is xlrd.XL_CELL_NUMBER:
                    is_float = cell.value % 1 != 0.0
                    values.append(
                        str(cell.value) if is_float else str(int(cell.value)))
                elif cell.ctype is xlrd.XL_CELL_DATE:
                    is_datetime = cell.value % 1 != 0.0
                    # emulate xldate_as_datetime for pre-0.9.3
                    dt = datetime.datetime(*xlrd.xldate.xldate_as_tuple(
                        cell.value, book.datemode))
                    values.append(
                        dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT
                                    ) if is_datetime else dt.
                        strftime(DEFAULT_SERVER_DATE_FORMAT))
                elif cell.ctype is xlrd.XL_CELL_BOOLEAN:
                    values.append(u'True' if cell.value else u'False')
                elif cell.ctype is xlrd.XL_CELL_ERROR:
                    raise ValueError(
                        _("Invalid cell value at row %(row)s, column %(col)s: %(cell_value)s"
                          ) % {
                              'row':
                              rowx,
                              'col':
                              colx,
                              'cell_value':
                              xlrd.error_text_from_code.get(
                                  cell.value,
                                  _("unknown error code %s") % cell.value)
                        })
                else:
                    values.append(cell.value)
            values_sheet.append(values)
        return values_sheet

    def import_pricelist_apply(self):
        ''' ------- Import Pricelist Using CSV and EXCEL ---------'''
        pricelist_obj = self.env['product.pricelist']
        pricelist_line_obj = self.env['product.pricelist.item']
        if self:
            for rec in self:
                if self.import_type == 'csv' or self.import_type == 'excel':
                    counter = 1
                    skipped_line_no = {}
                    try:
                        values = []
                        if self.import_type == 'csv':
                            # For CSV
                            file = str(
                                base64.decodebytes(self.file).decode('utf-8'))
                            values = csv.reader(file.splitlines())

                        elif self.import_type == 'excel':
                            # For EXCEL
                            values = self.read_xls_book()
                        skip_header = True
                        running_pricelist = None
                        created_pricelist = False
                        creted_price_list = []
                        for row in values:
                            try:
                                if skip_header:
                                    skip_header = False
                                    counter = counter + 1
                                    continue

                                if row[0] not in (None, "") and row[2] not in (None, ""):
                                    vals = {}
                                    domain = []

                                    if row[0] != running_pricelist:

                                        running_pricelist = row[0]

                                        pricelist_vals = {}
                                        if row[1] not in [None, ""]:
                                            pricelist_vals.update({
                                                'name': row[1],
                                                'company_id': self.company_id.id,
                                            })

                                            price_list_name = row[1]

                                            domain += [("name", "=", price_list_name),
                                                       ("company_id", "=", self.company_id.id)]
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Name is empty. "
                                            counter = counter + 1
                                            continue
                                        if self.sh_country_group_ids:
                                            pricelist_vals.update({
                                                'country_group_ids': [(6, 0, self.sh_country_group_ids.ids)]
                                            })

                                        if pricelist_vals:
                                            if self.import_by == 'add':
                                                created_pricelist = pricelist_obj.sudo().create(pricelist_vals)
                                                creted_price_list.append(
                                                    created_pricelist.id)

                                            if self.import_by == 'update':
                                                created_pricelist = pricelist_obj.sudo().search(domain)
                                                if self.sh_country_group_ids:
                                                    created_pricelist.sudo().write({
                                                        'country_group_ids': [(6, 0, self.sh_country_group_ids.ids)]
                                                    })
                                                for pricelist in created_pricelist:
                                                    creted_price_list.append(
                                                        pricelist.id)

                                                if not created_pricelist:
                                                    created_pricelist = pricelist_obj.sudo().create(pricelist_vals)
                                                    creted_price_list.append(
                                                        created_pricelist.id)
                                    if created_pricelist:

                                        vals = {}
                                        line_domain = []

                                        field_nm = 'name'
                                        if self.sh_applied_on != '2_product_category':
                                            if self.product_by == 'name':
                                                if self.sh_applied_on == '0_product_variant':
                                                    field_nm = 'sh_display_name'
                                                else:
                                                    field_nm = 'name'
                                            elif self.product_by == 'int_ref':
                                                field_nm = 'default_code'
                                            elif self.product_by == 'barcode':
                                                field_nm = 'barcode'
                                        if self.sh_applied_on == '2_product_category':
                                            search_category = self.env['product.category'].sudo().search(
                                                [('name', '=', row[2].strip())], limit=1)
                                            if search_category:
                                                vals.update(
                                                    {'categ_id': search_category.id})
                                                line_domain += [("categ_id",
                                                                 "=", search_category.id)]
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Category not found. "
                                                counter = counter + 1
                                                continue
                                        elif self.sh_applied_on == '1_product' and self.sh_applied_on != '2_product_category':
                                            search_product = self.env['product.template'].sudo().search(
                                                [(field_nm, '=', row[2].strip())], limit=1)
                                            if search_product:
                                                vals.update(
                                                    {'product_tmpl_id': search_product.id})
                                                line_domain += [("product_tmpl_id",
                                                                 "=", search_product.id)]
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Product not found. "
                                                counter = counter + 1
                                                continue
                                        elif self.sh_applied_on == '0_product_variant' and self.sh_applied_on != '2_product_category':
                                            search_product = self.env['product.product'].sudo().search(
                                                [(field_nm, '=', row[2].strip())], limit=1)
                                            if search_product:
                                                vals.update(
                                                    {'product_id': search_product.id})
                                                line_domain += [("product_id",
                                                                 "=", search_product.id)]
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Product Variant not found. "
                                                counter = counter + 1
                                                continue
                                        if row[3] not in [None, ""]:
                                            vals.update({
                                                'min_quantity': row[3],
                                            })
                                        if row[4] not in [None, ""]:
                                            cd = row[4]
                                            vals.update({
                                                'date_start': datetime.strptime(cd, '%Y-%m-%d').date()
                                            })
                                        if row[5] not in [None, ""]:
                                            cd = row[5]
                                            vals.update({
                                                'date_end': datetime.strptime(cd, '%Y-%m-%d').date()
                                            })
                                        if self.sh_compute_price == 'fixed':
                                            if row[6] not in [None, ""]:
                                                vals.update({
                                                    'fixed_price': row[6]
                                                })
                                        elif self.sh_compute_price == 'percentage':
                                            if row[7] not in [None, ""]:
                                                vals.update({
                                                    'percent_price': row[7]
                                                })
                                        elif self.sh_compute_price == 'formula':
                                            vals.update({
                                                'base': self.sh_base,
                                            })
                                            line_domain += [("base",
                                                             "=", self.sh_base)]

                                            if row[8] not in [None, ""]:
                                                vals.update({
                                                    'price_round': row[8]
                                                })
                                            if row[9] not in [None, ""]:
                                                vals.update({
                                                    'price_discount': row[9]
                                                })
                                            if row[10] not in [None, ""]:
                                                vals.update({
                                                    'price_min_margin': row[10]
                                                })
                                            if row[11] not in [None, ""]:
                                                vals.update({
                                                    'price_max_margin': row[11]
                                                })
                                            if row[12] not in [None, ""]:
                                                vals.update({
                                                    'price_surcharge': row[12]
                                                })
                                            if self.sh_base == 'pricelist':
                                                if row[13] not in [None, ""]:
                                                    other_pricelist_id = self.env['product.pricelist'].sudo().search(
                                                        [('name', '=', row[13])], limit=1)
                                                    if other_pricelist_id:
                                                        vals.update({
                                                            'base_pricelist_id': other_pricelist_id.id,
                                                        })
                                                    else:
                                                        skipped_line_no[str(
                                                            counter)] = " - Other Pricelist not found. "
                                                        counter = counter + 1
                                                        continue
                                                else:
                                                    skipped_line_no[str(
                                                        counter)] = " - Other Pricelist not found. "
                                                    counter = counter + 1
                                                    continue
                                        vals.update({
                                            'applied_on': self.sh_applied_on,
                                            'compute_price': self.sh_compute_price,
                                            'company_id': self.company_id.id,
                                        })

                                        if vals:

                                            line_domain += [("pricelist_id.name", "=", price_list_name), ("applied_on", "=",  self.sh_applied_on),
                                                            ("compute_price", "=", self.sh_compute_price), ("company_id", "=", self.company_id.id)]

                                            for pricelist in created_pricelist:
                                                new_domain = (
                                                    "pricelist_id.id", "=", pricelist.id)
                                                line_domain.append(
                                                    new_domain)
                                                vals.update({
                                                    'pricelist_id': pricelist.id,
                                                })

                                                if self.import_by == 'update':
                                                    lines = pricelist_line_obj.sudo().search(line_domain)
                                                    line_domain.remove(
                                                        new_domain)
                                                    if lines:
                                                        for line in lines:
                                                            line.sudo().write(vals)
                                                            counter = counter + 1
                                                    if not lines:
                                                        pricelist_line_obj.sudo().create(vals)
                                                        counter = counter + 1

                                                if self.import_by == 'add':
                                                    pricelist_line_obj.sudo().create(vals)
                                                    counter = counter + 1

                            except Exception as e:
                                skipped_line_no[str(
                                    counter)] = " - Value is not valid " + ustr(e)
                                counter = counter + 1
                                continue
                    except Exception as e:
                        raise UserError(
                            _("Sorry, Your file does not match with our format " + ustr(e)))
                    if counter > 1:
                        completed_records = len(creted_price_list)
                        res = self.show_success_msg(
                            completed_records, skipped_line_no)
                        return res
