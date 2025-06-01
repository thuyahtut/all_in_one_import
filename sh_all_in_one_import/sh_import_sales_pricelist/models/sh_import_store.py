# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from email.policy import default
from odoo import fields, models, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
from datetime import datetime
from odoo.tools import ustr
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT


class ImportStore(models.Model):
    _inherit = "sh.import.store"

    def check_sh_import_sale_pricelist(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_sales_pricelist':
            value = True
        return value

    sh_import_sale_pricelist_type = fields.Selection(
        related="base_id.sh_import_sale_pricelist_type", readonly=False, string="  Import File Type ", required=True)
    sh_import_sale_pricelist_by = fields.Selection(
        related="base_id.sh_import_sale_pricelist_by", readonly=False, string=" Import Pricelist By", required=True)
    sh_import_sale_pricelist_product_by = fields.Selection(string="Product By", required=True,readonly=False,related='base_id.sh_import_sale_pricelist_product_by')
    sh_import_sale_pricelist_boolean = fields.Boolean(
        "Import Sale Pricelist Boolean", default=check_sh_import_sale_pricelist)
    sh_company_id_sale_pricelist = fields.Many2one(
        related="base_id.sh_company_id_sale_pricelist", readonly=False, string="Company", required=True)
    sh_import_sale_pricelist_applied_on = fields.Selection(string="Applied On",related='base_id.sh_import_sale_pricelist_applied_on',readonly=False)
    sh_import_sale_pricelist_compute_price = fields.Selection(string="Compute Price", related='base_id.sh_import_sale_pricelist_compute_price',readonly=False)
    sh_import_sale_pricelist_country_group_ids = fields.Many2many(related='base_id.sh_import_sale_pricelist_country_group_ids',readonly=False,string="Country Groups")
    sh_import_sale_pricelist_base = fields.Selection(related='base_id.sh_import_sale_pricelist_base',readonly=False,string='Based On')
    running_so_pricelist = fields.Char(string='Running So Pricelist')
    total_done_so_pricelist = fields.Integer("Total Done SO Pricelist")

    def create_sales_pricelist_logs(self, counter, skipped_line_no,confirm_records):
        # dic_msg = str(counter) + " Records imported successfully"
        dic_msg = str(confirm_records) + " Rows imported successfully" 
        if skipped_line_no:
            dic_msg = dic_msg + "\nNote:"
        for k, v in skipped_line_no.items():
            dic_msg = dic_msg + "\nRow No " + k + " " + v + " "
        self.env['sh.import.log'].create({
            'message': dic_msg,
            'datetime': datetime.now(),
            'sh_store_id': self.id
        })

    def read_xls_book(self):
        book = xlrd.open_workbook(file_contents=base64.decodebytes(self.sh_file))
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

    def perform_the_action(self, record):
        res = super(ImportStore, self).perform_the_action(record)
        if record.base_id.sh_technical_name == 'sh_import_sales_pricelist':
            self.import_sales_pricelist(record)
        return res

    def import_sales_pricelist(self,record):
        self = record
        pricelist_obj = self.env['product.pricelist']
        pricelist_line_obj = self.env['product.pricelist.item']

        # # perform import task
        if self and self.sh_file:

            if self.sh_import_sale_pricelist_type == 'csv' or self.sh_import_sale_pricelist_type == 'excel':
                counter = 1
                skipped_line_no = {}
                count=0
                imported_lines = 0
                try:
                    if self.sh_import_sale_pricelist_type == 'csv':
                        sh_file = str(base64.decodebytes(
                            self.sh_file).decode('utf-8'))
                        length_r = csv.reader(sh_file.splitlines())
                        length_reader = len(list(length_r))
                        myreader = csv.reader(sh_file.splitlines())
                        myreader = list(myreader)                       
                    elif self.sh_import_sale_pricelist_type == 'excel':
                        myreader=self.read_xls_book()                       
                        length_reader = len(myreader)

                    skip_header = True
                    till = length_reader
                    # running_pricelist = None
                    created_pricelist = False
                    creted_price_list = []
                    if self.import_limit == 0 or self.count_start_from+self.import_limit > length_reader:
                        till = length_reader
                    else:
                        till = self.count_start_from+self.import_limit
                    self.total_done_so_pricelist = till    
                    for row in range(self.count_start_from - 1, till):
                        try:
                            created_pricelist = pricelist_obj.sudo().search([('name','=',self.running_so_pricelist)],limit=1)
                            row = myreader[row] 
                            count += 1 
                            self.current_count += 1                                                       
                            if count == self.import_limit:
                                self.count_start_from += self.import_limit   
                            if skip_header:   
                                skip_header = False
                                continue
                            if row[0] not in (None, "") and row[2] not in (None, ""):
                                vals = {}
                                domain = []

                                if row[0] != self.running_so_pricelist:

                                    self.running_so_pricelist = row[0]

                                    pricelist_vals = {}
                                    if row[1] not in [None, ""]:
                                        pricelist_vals.update({
                                            'name': row[1],
                                            'company_id': self.sh_company_id_sale_pricelist.id,
                                        })

                                        price_list_name = row[1]

                                        domain += [("name", "=", price_list_name),
                                                    ("company_id", "=", self.sh_company_id_sale_pricelist.id)]
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Name is empty. "
                                        counter = counter + 1
                                        continue
                                    if self.sh_import_sale_pricelist_country_group_ids:
                                        pricelist_vals.update({
                                            'country_group_ids': [(6, 0, self.sh_import_sale_pricelist_country_group_ids.ids)]
                                        })

                                    if pricelist_vals:
                                        if self.sh_import_sale_pricelist_by == 'add':
                                            created_pricelist = pricelist_obj.sudo().create(pricelist_vals)
                                            creted_price_list.append(
                                                created_pricelist.id)

                                        if self.sh_import_sale_pricelist_by == 'update':
                                            created_pricelist = pricelist_obj.sudo().search(domain)
                                            if self.sh_import_sale_pricelist_country_group_ids:
                                                created_pricelist.sudo().write({
                                                    'country_group_ids': [(6, 0, self.sh_import_sale_pricelist_country_group_ids.ids)]
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
                                    if self.sh_import_sale_pricelist_applied_on != '2_product_category':
                                        if self.sh_import_sale_pricelist_product_by == 'name':
                                            if self.sh_import_sale_pricelist_applied_on == '0_product_variant':
                                                field_nm = 'sh_display_name'
                                            else:
                                                field_nm = 'name'
                                        elif self.sh_import_sale_pricelist_product_by == 'int_ref':
                                            field_nm = 'default_code'
                                        elif self.sh_import_sale_pricelist_product_by == 'barcode':
                                            field_nm = 'barcode'
                                    if self.sh_import_sale_pricelist_applied_on == '2_product_category':
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
                                    elif self.sh_import_sale_pricelist_applied_on == '1_product' and self.sh_import_sale_pricelist_applied_on != '2_product_category':
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
                                    elif self.sh_import_sale_pricelist_applied_on == '0_product_variant' and self.sh_import_sale_pricelist_applied_on != '2_product_category':
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
                                            'date_start': datetime.strptime(cd, DEFAULT_SERVER_DATE_FORMAT).date()
                                        })
                                    if row[5] not in [None, ""]:
                                        cd = row[5]
                                        vals.update({
                                            'date_end': datetime.strptime(cd, DEFAULT_SERVER_DATE_FORMAT).date()
                                        })
                                    if self.sh_import_sale_pricelist_compute_price == 'fixed':
                                        if row[6] not in [None, ""]:
                                            vals.update({
                                                'fixed_price': row[6]
                                            })
                                    elif self.sh_import_sale_pricelist_compute_price == 'percentage':
                                        if row[7] not in [None, ""]:
                                            vals.update({
                                                'percent_price': row[7]
                                            })
                                    elif self.sh_import_sale_pricelist_compute_price == 'formula':
                                        vals.update({
                                            'base': self.sh_import_sale_pricelist_base,
                                        })
                                        line_domain += [("base","=", self.sh_import_sale_pricelist_base)]

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
                                        if self.sh_import_sale_pricelist_base == 'pricelist':
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
                                        'applied_on': self.sh_import_sale_pricelist_applied_on,
                                        'compute_price': self.sh_import_sale_pricelist_compute_price,
                                        'company_id': self.sh_company_id_sale_pricelist.id,
                                    })

                                    if vals:

                                        line_domain += [("pricelist_id.name", "=", price_list_name), ("applied_on", "=",  self.sh_import_sale_pricelist_applied_on),
                                                        ("compute_price", "=", self.sh_import_sale_pricelist_compute_price), ("company_id", "=", self.sh_company_id_sale_pricelist.id)]

                                        for pricelist in created_pricelist:
                                            new_domain = (
                                                "pricelist_id.id", "=", pricelist.id)
                                            line_domain.append(
                                                new_domain)
                                            vals.update({
                                                'pricelist_id': pricelist.id,
                                            })

                                            if self.sh_import_sale_pricelist_by == 'update':
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

                                            if self.sh_import_sale_pricelist_by == 'add':
                                                pricelist_line_obj.sudo().create(vals)
                                                counter = counter + 1
                            imported_lines += 1
                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid. " + ustr(e)
                            counter = counter + 1
                            continue
                except Exception as e:
                    raise UserError(
                        _("Sorry, Your csv or excel file does not match with our format"
                        + ustr(e)))
                # if length_reader == self.total_done_so_pricelist:
                #     if not skipped_line_no:
                #         self.create_logs(
                #             self.total_done_so_pricelist, skipped_line_no,0)
                #         self.state = 'done'
                if counter > 1:
                    completed_records = (counter - len(skipped_line_no)) - 1
                #     if not skipped_line_no:
                #         self.create_sales_pricelist_logs(
                #             completed_records, skipped_line_no)
                #         self.state = 'done'
                #     else:
                #         self.received_error = True
                #         self.create_sales_pricelist_logs(
                #             completed_records, skipped_line_no)
                #         if self.on_error == 'break':
                #             self.state = 'error'
                #         elif self.import_limit == 0:
                #             if self.received_error:
                #                 self.state = 'partial_done'
                #             else:
                #                 self.state = 'done'
                    if not skipped_line_no:
                        self.create_sales_pricelist_logs(
                            completed_records, skipped_line_no,imported_lines)
                        # if self.received_error:
                        #     self.state = 'partial_done'
                        # else:
                        self.state = 'done' if length_reader == self.total_done_so_pricelist else 'running'
                    else:
                        self.received_error = True
                        self.create_sales_pricelist_logs(
                            completed_records, skipped_line_no,imported_lines)
                        if self.on_error == 'break':
                            self.state = 'error'
                        elif self.import_limit == 0:
                            if self.received_error:
                                self.state = 'partial_done'
                            else:
                                self.state = 'done' if length_reader == self.total_done_so_pricelist else None
