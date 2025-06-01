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

    def check_sh_import_so(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_so':
            value = True
        return value

    sh_import_so_type = fields.Selection(related="base_id.sh_import_so_type",string="Import File Type", required=True,readonly=False)
    sh_import_so_product_by = fields.Selection(related='base_id.sh_import_so_product_by',string="Product By", required=True,readonly=False)
    sh_import_so_is_create_customer = fields.Boolean(related='base_id.sh_import_so_is_create_customer',string="Create Customer?",readonly=False)
    sh_import_so_is_confirm_sale = fields.Boolean(related='base_id.sh_import_so_is_confirm_sale',string="Auto Confirm Sale?",readonly=False)
    sh_import_so_order_no_type = fields.Selection(related='base_id.sh_import_so_order_no_type',readonly=False,string="Quotation/Order Number", required=True)
    sh_import_so_unit_price = fields.Selection(related='base_id.sh_import_so_unit_price',readonly=False,string="Unit Price", required=True)
    sh_import_so_partner_by = fields.Selection(related='base_id.sh_import_so_partner_by',readonly=False,string="Customer By")
    sh_import_so_boolean = fields.Boolean(
        "Import Sale Order Boolean", default=check_sh_import_so)
    sh_company_id_so = fields.Many2one(
        related="base_id.sh_company_id_so", readonly=False, string="Company", required=True)
    running_so = fields.Char(string='Running So')
    total_done_so = fields.Integer("Total Done SO")

    def create_so_logs(self, counter, skipped_line_no,confirm_records):
        # dic_msg = str(counter) + " Records imported successfully"+"\n"
        dic_msg = str(confirm_records) + " Rows imported successfully"+"\n"
        # dic_msg = dic_msg + str(confirm_records) + " Records Confirm"
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
        if record.base_id.sh_technical_name == 'sh_import_so':
            self.import_so(record)
        return res

    def import_so(self,record):
        self = record
        sol_obj = self.env['sale.order.line']
        sale_order_obj = self.env['sale.order']

        # # perform import SO
        if self and self.sh_file:

            if self.sh_import_so_type == 'csv' or self.sh_import_so_type == 'excel':
                counter = 1
                skipped_line_no = {}
                count=0
                created_so_list = []
                created_so_list_for_confirm = []
                imported_lines = 0
                try:
                    if self.sh_import_so_type == 'csv':
                        sh_file = str(base64.decodebytes(
                            self.sh_file).decode('utf-8'))
                        length_r = csv.reader(sh_file.splitlines())
                        length_reader = len(list(length_r))
                        myreader = csv.reader(sh_file.splitlines())
                        myreader = list(myreader)                       
                    elif self.sh_import_so_type == 'excel':
                        myreader=self.read_xls_book()                       
                        length_reader = len(myreader)

                    skip_header = True
                    till = length_reader
                    created_so = False
                    
                    
                    if self.import_limit == 0 or self.count_start_from+self.import_limit > length_reader:
                        till = length_reader
                    else:
                        till = self.count_start_from+self.import_limit

                    self.total_done_so = till

                    for row in range(self.count_start_from - 1, till):
                        try:
                            created_so = self.env['sale.order'].sudo().search([('name','=',self.running_so)],limit=1)
                            row = myreader[row] 
                            count += 1 
                            self.current_count += 1                                                       
                            if count == self.import_limit:
                                self.count_start_from += self.import_limit   
                            if skip_header:   
                                skip_header = False
                                continue
                            if row[0] not in (None, "") and row[4] not in (None, ""):
                                vals = {}
                                domain = []

                                if row[0] != self.running_so:

                                    self.running_so = row[0]
                                    so_vals = {
                                        'company_id': self.sh_company_id_so.id}

                                    if row[1] not in (None, ""):
                                        partner_obj = self.env["res.partner"]
                                        if self.sh_import_so_partner_by == 'name':
                                            domain += [('name',
                                                        '=', row[1])]
                                            customer_dic = {'name': row[1]}
                                        if self.sh_import_so_partner_by == 'ref':
                                            domain += [('ref',
                                                        '=', row[1])]
                                            customer_dic = {
                                                'ref': row[1], 'name': row[1]}
                                        if self.sh_import_so_partner_by == 'id':
                                            domain += [('id', '=', row[1])]
                                            customer_dic = {
                                                'id': row[1], 'name': row[1]}

                                        partner = partner_obj.search(
                                            domain, limit=1)

                                        if partner:
                                            so_vals.update(
                                                {'partner_id': partner.id})
                                        elif self.sh_import_so_is_create_customer:
                                            customer_dic.update({'company_type': 'person',
                                                                    'customer_rank': 1,
                                                                    })
                                            partner = partner_obj.create(
                                                customer_dic)
                                            if not partner:
                                                skipped_line_no[str(
                                                    counter)] = " - Customer not created. "
                                                counter = counter + 1
                                                continue
                                            else:
                                                so_vals.update(
                                                    {'partner_id': partner.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Customer not found. "
                                            counter = counter + 1
                                            continue
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Customer field is empty. "
                                        counter = counter + 1
                                        continue

                                    if row[2] not in (None, ""):
                                        cd = row[2]
                                        cd = str(datetime.strptime(
                                            cd, DEFAULT_SERVER_DATE_FORMAT).date())
                                        so_vals.update({'date_order': cd})

                                    if row[3] not in (None, ""):
                                        search_user = self.env['res.users'].search(
                                            [('name', '=', row[3])], limit=1)
                                        if search_user:
                                            so_vals.update(
                                                {'user_id': search_user.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Salesperson not found. "
                                            counter = counter + 1
                                            continue

                                    if self.sh_import_so_order_no_type == 'as_per_sheet':
                                        so_vals.update({"name": row[0]})
                                    created_so = sale_order_obj.create(
                                        so_vals)                                        
                                    created_so_list_for_confirm.append(
                                        created_so.id)
                                    created_so_list.append(created_so.id)
                                if created_so:
                                    field_nm = 'name'
                                    if self.sh_import_so_product_by == 'name':
                                        field_nm = 'name'
                                    elif self.sh_import_so_product_by == 'int_ref':
                                        field_nm = 'default_code'
                                    elif self.sh_import_so_product_by == 'barcode':
                                        field_nm = 'barcode'

                                    search_product = self.env['product.product'].search(
                                        [(field_nm, '=', row[4])], limit=1)
                                    if search_product:
                                        vals.update(
                                            {'product_id': search_product.id})

                                        if row[5] != '':
                                            vals.update({'name': row[5]})

                                        if row[6] != '':
                                            vals.update(
                                                {'product_uom_qty': float(row[6])})
                                        else:
                                            vals.update(
                                                {'product_uom_qty': 1.00})

                                        if row[7] in (None, "") and search_product.uom_id:
                                            vals.update(
                                                {'product_uom': search_product.uom_id.id})
                                        else:
                                            search_uom = self.env['uom.uom'].search(
                                                [('name', '=', row[7])], limit=1)
                                            if search_uom:
                                                vals.update(
                                                    {'product_uom': search_uom.id})
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Unit of Measure not found. "
                                                counter = counter + 1
                                                if created_so.id in created_so_list_for_confirm:
                                                    created_so_list_for_confirm.remove(
                                                        created_so.id)
                                                continue

                                        if row[8] in (None, ""):
                                            vals.update(
                                                {'price_unit': search_product.lst_price})
                                        else:
                                            vals.update(
                                                {'price_unit': float(row[8])})

                                        if row[9].strip() in (None, "") and search_product.taxes_id:
                                            vals.update(
                                                {'tax_id': [(6, 0, search_product.taxes_id.ids)]})
                                        else:
                                            taxes_list = []
                                            some_taxes_not_found = False
                                            for x in row[9].split(','):
                                                x = x.strip()
                                                if x != '':
                                                    search_tax = self.env['account.tax'].search(
                                                        [('name', '=', x)], limit=1)
                                                    if search_tax:
                                                        taxes_list.append(
                                                            search_tax.id)
                                                    else:
                                                        some_taxes_not_found = True
                                                        skipped_line_no[str(
                                                            counter)] = " - Taxes " + x + " not found. "
                                                        break
                                            if some_taxes_not_found:
                                                counter = counter + 1
                                                if created_so.id in created_so_list_for_confirm:
                                                    created_so_list_for_confirm.remove(
                                                        created_so.id)
                                                continue
                                            else:
                                                vals.update(
                                                    {'tax_id': [(6, 0, taxes_list)]})
                                        if row[10] not in (None, ""):
                                            vals.update(
                                                {'discount': float(row[10])})
                                        vals.update(
                                            {'order_id': created_so.id})
                                        line = sol_obj.create(vals)
                                        counter = counter + 1

                                        if self.sh_import_so_unit_price == 'pricelist':
                                            line._compute_price_unit()

                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Product not found. "
                                        counter = counter + 1
                                        if created_so.id in created_so_list_for_confirm:
                                            created_so_list_for_confirm.remove(
                                                created_so.id)
                                        continue

                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Order not created. "
                                    counter = counter + 1
                                    continue

                            else:
                                skipped_line_no[str(
                                    counter)] = " - Sales Order or Product field is empty. "
                                counter = counter + 1
                            imported_lines += 1
                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid. " + ustr(e)
                            counter = counter + 1
                            continue
                    # if created_so_list_for_confirm and self.sh_import_so_is_confirm_sale:
                    #     sale_orders = sale_order_obj.search(
                    #         [('id', 'in', created_so_list_for_confirm)])
                    #     if sale_orders:
                    #         for sale_order in sale_orders:
                    #             sale_order.action_confirm()                                                                            
                    # else:
                    #     created_so_list_for_confirm = []
                except Exception as e:
                    raise UserError(
                        _("Sorry, Your csv or excel file does not match with our format"
                        + ustr(e)))
                # if length_reader == self.total_done_so:
                #     if not skipped_line_no:
                #         self.create_so_logs(
                #             self.total_done_so, skipped_line_no,0)
                #         self.state = 'done'
                if counter > 1:
                    completed_records = len(created_so_list)
                #     confirm_records = len(created_so_list_for_confirm)
                #     if not skipped_line_no:
                #         self.create_so_logs(
                #             completed_records, skipped_line_no,confirm_records)
                #         self.state = 'done'
                #     else:
                #         self.received_error = True
                #         self.create_so_logs(
                #             completed_records, skipped_line_no,confirm_records)
                #         if self.on_error == 'break':
                #             self.state = 'error'
                #         elif self.import_limit == 0:
                #             if self.received_error:
                #                 self.state = 'partial_done'
                #             else:
                #                 self.state = 'done'
                    if not skipped_line_no:
                        self.create_so_logs(
                            completed_records, skipped_line_no,imported_lines)
                        # if self.received_error:
                        #     self.state = 'partial_done'
                        # else:
                        self.state = 'done' if length_reader == self.total_done_so else 'running'
                    else:
                        self.received_error = True
                        self.create_so_logs(
                            completed_records, skipped_line_no,imported_lines)
                        if self.on_error == 'break':
                            self.state = 'error'
                        elif self.import_limit == 0:
                            if self.received_error:
                                self.state = 'partial_done'
                            else:
                                self.state = 'done' if length_reader == self.total_done_so else None