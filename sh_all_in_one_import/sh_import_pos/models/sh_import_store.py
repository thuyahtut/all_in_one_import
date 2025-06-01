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

    def check_sh_import_pos(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_pos':
            value = True
        return value

    sh_import_pos_type = fields.Selection(related='base_id.sh_import_pos_type',readonly=False, string="Import File Type", required=True)
    sh_import_pos_product_by = fields.Selection(related='base_id.sh_import_pos_product_by',readonly=False, string="Product By", required=True)
    sh_import_pos_is_create_customer = fields.Boolean(related='base_id.sh_import_pos_is_create_customer',readonly=False,string="Create Customer?")
    sh_import_pos_order_no_type = fields.Selection(related='base_id.sh_import_pos_order_no_type',readonly=False, string="POS Order Number", required=True)
    sh_import_pos_partner_by = fields.Selection(related='base_id.sh_import_pos_partner_by',readonly=False, string="Customer By")
    sh_import_pos_boolean = fields.Boolean(
        "Import POS Order Boolean", default=check_sh_import_pos)
    sh_company_id_pos = fields.Many2one(
        related="base_id.sh_company_id_pos", readonly=False, string="Company", required=True)
    running_pos = fields.Char(string='Running POS')
    total_done_pos = fields.Integer("Total Done POS")

    def create_pos_logs(self, counter, skipped_line_no,imported_lines):
        dic_msg = str(imported_lines) + " Rows imported successfully"

        # dic_msg = str(counter) + " Records imported successfully"
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
        if record.base_id.sh_technical_name == 'sh_import_pos':
            self.import_pos(record)
        return res

    def import_pos(self,record):
        self = record
        pos_line_obj = self.env['pos.order.line']
        pos_order_obj = self.env['pos.order']

        # # perform import SO
        if self and self.sh_file:

            if self.sh_import_pos_type == 'csv' or self.sh_import_pos_type == 'excel':
                counter = 1
                skipped_line_no = {}
                count=0
                imported_lines = 0
                created_pos_list = []
                try:
                    if self.sh_import_pos_type == 'csv':
                        sh_file = str(base64.decodebytes(
                            self.sh_file).decode('utf-8'))
                        length_r = csv.reader(sh_file.splitlines())
                        length_reader = len(list(length_r))
                        myreader = csv.reader(sh_file.splitlines())
                        myreader = list(myreader)                       
                    elif self.sh_import_pos_type == 'excel':
                        myreader=self.read_xls_book()                       
                        length_reader = len(myreader)

                    skip_header = True
                    till = length_reader
                    # running_pos = None
                    # created_pos = False
                    if self.import_limit == 0 or self.count_start_from+self.import_limit > length_reader:
                        till = length_reader
                    else:
                        till = self.count_start_from+self.import_limit
                    self.total_done_pos = till

                    for row in range(self.count_start_from - 1, till):
                        try:
                            created_pos = pos_order_obj.sudo().search([('name','=',self.running_pos)],limit=1)
                            row = myreader[row] 
                            count += 1 
                            self.current_count += 1                                                       
                            if count == self.import_limit:
                                self.count_start_from += self.import_limit   
                            if skip_header:   
                                skip_header = False
                                continue
                            if row[0] not in (None, "") and row[5] not in (None, ""):
                                vals = {}

                                if row[0] != self.running_pos:

                                    self.running_pos = row[0]
                                    pos_vals = {}
                                    
                                    if row[1] not in (None, ""):
                                        search_session = self.env['pos.session'].search(
                                            [('name', '=', row[1])], limit=1)
                                        if search_session:
                                            pos_vals.update(
                                                {'session_id': search_session.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Session not found. "
                                            counter = counter + 1
                                            continue

                                    if row[2] not in (None, ""):
                                        partner_obj = self.env["res.partner"]
                                        domain = []
                                        if self.sh_import_pos_partner_by == 'name':
                                            domain += [('name',
                                                        '=', row[2])]
                                        if self.sh_import_pos_partner_by == 'ref':
                                            domain += [('ref',
                                                        '=', row[2])]
                                        if self.sh_import_pos_partner_by == 'id':
                                            domain += [('id', '=', row[2])]
                                        
                                        partner = partner_obj.search(
                                            domain, limit=1)

                                        if partner:
                                            pos_vals.update(
                                                {'partner_id': partner.id})
                                        elif self.sh_import_pos_is_create_customer:
                                            partner = partner_obj.create({'company_type': 'person',
                                                                            'name': row[2],
                                                                            'customer_rank': 1,
                                                                            })
                                            if not partner:
                                                skipped_line_no[str(
                                                    counter)] = " - Customer not created. "
                                                counter = counter + 1
                                                continue
                                            else:
                                                pos_vals.update(
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

                                    if row[3] not in (None, ""):
                                        cd = row[3]
                                        cd = str(datetime.strptime(
                                            cd, DEFAULT_SERVER_DATE_FORMAT).date())
                                        pos_vals.update({'date_order': cd})

                                    if row[4] not in (None, ""):
                                        search_user = self.env['res.users'].search(
                                            [('name', '=', row[4])], limit=1)
                                        if search_user:
                                            pos_vals.update(
                                                {'user_id': search_user.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - User not found. "
                                            counter = counter + 1
                                            continue
                                    pos_vals.update({'amount_tax': 0.0})
                                    pos_vals.update({'amount_total': 0.0})
                                    pos_vals.update(
                                        {'company_id': self.env.user.company_id.id})
                                    pos_vals.update({'amount_paid': 0.0})
                                    pos_vals.update({'amount_return': 0.0})
                                    if self.sh_import_pos_order_no_type == 'as_per_sheet':
                                        pos_vals.update({"name": row[0]})
                                    created_pos = pos_order_obj.create(
                                        pos_vals)
                                    created_pos._onchange_amount_all()
                                    created_pos._compute_batch_amount_all()
                                    created_pos_list.append(created_pos.id)

                                if created_pos:

                                    field_nm = 'name'
                                    if self.sh_import_pos_product_by == 'name':
                                        field_nm = 'name'
                                    elif self.sh_import_pos_product_by == 'int_ref':
                                        field_nm = 'default_code'
                                    elif self.sh_imrunning_soport_pos_product_by == 'barcode':
                                        field_nm = 'barcode'

                                    search_product = self.env['product.product'].search(
                                        [(field_nm, '=', row[5])], limit=1)
                                    if search_product:
                                        vals.update(
                                            {'product_id': search_product.id,
                                                'full_product_name': search_product.display_name})

                                        if row[6] != '':
                                            vals.update({'name': row[6]})

                                        if row[7] != '':
                                            vals.update({'qty': row[7]})
                                        else:
                                            vals.update({'qty': 1})

                                        if row[8] in (None, "") and search_product.uom_id:
                                            vals.update(
                                                {'product_uom_id': search_product.uom_id.id})
                                        else:
                                            search_uom = self.env['uom.uom'].search(
                                                [('name', '=', row[8])], limit=1)
                                            if search_uom:
                                                vals.update(
                                                    {'product_uom_id': search_uom.id})
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Unit of Measure not found. "
                                                counter = counter + 1
                                                continue

                                        if row[9] in (None, ""):
                                            vals.update(
                                                {'price_unit': search_product.lst_price})
                                        else:
                                            vals.update(
                                                {'price_unit': row[9]})

                                        if row[10].strip() in (None, "") and search_product.taxes_id:
                                            vals.update(
                                                {'tax_ids': [(6, 0, search_product.taxes_id.ids)]})
                                        else:
                                            taxes_list = []
                                            some_taxes_not_found = False
                                            for x in row[10].split(','):
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
                                                continue
                                            else:
                                                if taxes_list:
                                                    vals.update(
                                                        {'tax_ids': [(6, 0, taxes_list)]})
                                                else:
                                                    vals.update(
                                                        {'tax_ids': [(6, 0, '')]})
                                        vals.update({'price_subtotal': float(
                                            row[9]) * float(row[7]), 'price_subtotal_incl': float(row[9]) * float(row[7])})
                                        vals.update(
                                            {'order_id': created_pos.id})
                                        line = pos_line_obj.create(vals)

                                        line.order_id._compute_batch_amount_all()
                                        line.order_id._onchange_amount_all()
                                        line.order_id._compute_order_name()

                                        counter = counter + 1

                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Product not found. "
                                        counter = counter + 1
                                        continue

                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Order not created. "
                                    counter = counter + 1
                                    continue

                            else:
                                skipped_line_no[str(
                                    counter)] = " - POS Order or Product field is empty. "
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
                # if length_reader == self.total_done_pos:
                #     if not skipped_line_no:
                #         self.create_logs(
                #             self.total_done_pos, skipped_line_no,0)
                #         self.state = 'done'
                if counter > 1:
                    completed_records = len(created_pos_list)
                    if not skipped_line_no:
                        self.create_pos_logs(
                            completed_records, skipped_line_no,imported_lines)
                        self.state = 'done'
                    else:
                        self.received_error = True
                        self.create_pos_logs(
                            completed_records, skipped_line_no,imported_lines)
                        if self.on_error == 'break':
                            self.state = 'error'
                        elif self.import_limit == 0:
                            if self.received_error:
                                self.state = 'partial_done'
                            else:
                                self.state = 'done'
