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

    def check_sh_import_po(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_po':
            value = True
        return value

    sh_import_po_type = fields.Selection(related='base_id.sh_import_po_type',readonly=False,string="Import File Type", required=True)
    sh_import_po_product_by = fields.Selection(related='base_id.sh_import_po_product_by',readonly=False, string="Product By", required=True)
    sh_import_po_is_create_vendor = fields.Boolean(related='base_id.sh_import_po_is_create_vendor',readonly=False,string="Create Vendor?")
    sh_import_po_is_confirm_order = fields.Boolean(related='base_id.sh_import_po_is_confirm_order',readonly=False,string="Auto Confirm Order?")
    sh_import_po_order_no_type = fields.Selection(related='base_id.sh_import_po_order_no_type',readonly=False, string="Reference Number", required=True)
    sh_import_po_unit_price = fields.Selection(related='base_id.sh_import_po_unit_price',readonly=False, string="Unit Price", required=True)
    sh_import_po_partner_by = fields.Selection(related='base_id.sh_import_po_partner_by',readonly=False, string="Vendor By")
    sh_import_po_boolean = fields.Boolean(
        "Import PO Order Boolean", default=check_sh_import_po)
    sh_company_id_po = fields.Many2one(
        related="base_id.sh_company_id_po", readonly=False, string="Company", required=True)
    running_po = fields.Char(string='Running Po')
    total_done_po = fields.Integer("Total Done")

    def create_po_logs(self, counter, skipped_line_no,confirm_records):
        # dic_msg = str(counter) + " Records imported successfully"+"\n"
        # dic_msg = dic_msg + str(confirm_records) + " Records Confirm"
        # dic_msg = ''
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
        if record.base_id.sh_technical_name == 'sh_import_po':
            self.import_po(record)
        return res

    def import_po(self,record):
        self = record
        pol_obj = self.env['purchase.order.line']
        purchase_order_obj = self.env['purchase.order']

        # # perform import SO
        if self and self.sh_file:

            if self.sh_import_po_type == 'csv' or self.sh_import_po_type == 'excel':
                counter = 1
                skipped_line_no = {}
                count = 0
                created_po_list_for_confirm = []
                created_po_list = []
                imported_lines = 0
                try:
                    if self.sh_import_po_type == 'csv':
                        sh_file = str(base64.decodebytes(
                            self.sh_file).decode('utf-8'))
                        length_r = csv.reader(sh_file.splitlines())
                        length_reader = len(list(length_r))
                        myreader = csv.reader(sh_file.splitlines())
                        myreader = list(myreader)                       
                    elif self.sh_import_po_type == 'excel':
                        myreader=self.read_xls_book()                       
                        length_reader = len(myreader)

                    skip_header = True
                    till = length_reader
                    created_po = False
                    
                    
                    if self.import_limit == 0 or self.count_start_from+self.import_limit > length_reader:
                        till = length_reader
                    else:
                        till = self.count_start_from+self.import_limit
                    self.total_done_po = till
                    for row in range(self.count_start_from - 1, till):
                        row = myreader[row] 
                        if skip_header: 
                            skip_header = False
                            counter = counter + 1
                            continue
                        count += 1 
                        self.current_count += 1                                                       
                        if count == self.import_limit:
                            self.count_start_from += self.import_limit   
                        
                        try:
                            created_po = self.env['purchase.order'].sudo().search([('name','=',self.running_po)],limit=1)
                            if row[0] not in (None, "") and row[4] not in (None, ""):
                                vals = {}
                                domain = []

                                if row[0] != self.running_po:

                                    self.running_po = row[0]
                                    po_vals = {
                                        'company_id': self.sh_company_id_po.id}
			                       

                                    if row[1] not in (None, ""):
                                        partner_obj = self.env["res.partner"]

                                        if self.sh_import_po_partner_by == 'name':
                                            domain += [('name', '=', row[1])]
                                            vendor_dic = {'name': row[1]}
                                        if self.sh_import_po_partner_by == 'ref':
                                            domain += [('ref', '=', row[1])]
                                            vendor_dic = {
                                                'ref': row[1], 'name': row[1]}
                                        if self.sh_import_po_partner_by == 'id':
                                            domain += [('id', '=', row[1])]
                                            vendor_dic = {
                                                'id': row[1], 'name': row[1]}

                                        partner = partner_obj.search(
                                            domain, limit=1)

                                        if partner:
                                            po_vals.update(
                                                {'partner_id': partner.id})
                                        elif self.sh_import_po_is_create_vendor:
                                            vendor_dic.update({'company_type': 'person',
                                                               'supplier_rank': 1,
                                                               'customer_rank': 0,
                                                               })
                                            partner = partner_obj.create(
                                                vendor_dic)

                                            if not partner:
                                                skipped_line_no[str(
                                                    counter)] = " - Vendor not created. "
                                                counter = counter + 1
                                                continue
                                            else:
                                                po_vals.update(
                                                    {'partner_id': partner.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Vendor not found. "
                                            counter = counter + 1
                                            continue
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Vendor field is empty. "
                                        counter = counter + 1
                                        continue

                                    if row[2] not in (None, ""):
                                        cd = row[2]
                                        cd = str(datetime.strptime(
                                            cd, DEFAULT_SERVER_DATE_FORMAT).date())
                                        po_vals.update({'date_order': cd})
                                    else:
                                        po_vals.update(
                                            {'date_order': datetime.now()})

                                    if row[3] not in (None, ""):
                                        cd = row[3]
                                        cd = str(datetime.strptime(
                                            cd, DEFAULT_SERVER_DATE_FORMAT).date())
                                        po_vals.update({'date_planned': cd})

                                    if self.sh_import_po_order_no_type == 'as_per_sheet':
                                        po_vals.update({"name": row[0]})
                                    created_po = purchase_order_obj.create(
                                        po_vals)
                                    created_po_list_for_confirm.append(
                                        created_po.id)
                                    created_po_list.append(created_po.id)

                                if created_po:

                                    field_nm = 'name'
                                    if self.sh_import_po_product_by == 'name':
                                        field_nm = 'name'
                                    elif self.sh_import_po_product_by == 'int_ref':
                                        field_nm = 'default_code'
                                    elif self.sh_import_po_product_by == 'barcode':
                                        field_nm = 'barcode'

                                    search_product = self.env['product.product'].search(
                                        [(field_nm, '=', row[4])], limit=1)
                                    if search_product:

                                        vals.update(
                                            {'product_id': search_product.id})

                                        if row[5] != '':
                                            vals.update({'name': row[5]})
                                        else:
                                            product_lang = search_product.with_context({
                                                'lang': created_po.partner_id.lang,
                                                'partner_id': created_po.partner_id.id,
                                            })
                                            pro_desc = product_lang.display_name
                                            if product_lang.description_purchase:
                                                pro_desc += '\n' + product_lang.description_purchase
                                            vals.update({'name': pro_desc})

                                        if not vals.get('name', False):
                                            vals.update(
                                                {'name': search_product.name})

                                        if row[6] != '':
                                            vals.update(
                                                {'product_qty': row[6]})
                                        else:
                                            vals.update({'product_qty': 1})

                                        if row[7] in (None, "") and search_product.uom_po_id:
                                            vals.update(
                                                {'product_uom': search_product.uom_po_id.id})
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
                                                if created_po.id in created_po_list_for_confirm:
                                                    created_po_list_for_confirm.remove(
                                                        created_po.id)
                                                continue

                                        if row[8] in (None, ""):
                                            vals.update(
                                                {'price_unit': search_product.standard_price})
                                        else:
                                            vals.update({'price_unit': row[8]})

                                        if row[9].strip() in (None, "") and search_product.supplier_taxes_id:
                                            vals.update(
                                                {'taxes_id': [(6, 0, search_product.supplier_taxes_id.ids)]})
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
                                                if created_po.id in created_po_list_for_confirm:
                                                    created_po_list_for_confirm.remove(
                                                        created_po.id)
                                                continue
                                            else:
                                                vals.update(
                                                    {'taxes_id': [(6, 0, taxes_list)]})

                                        if row[10] in (None, ""):
                                            vals.update(
                                                {'date_planned': datetime.now()})
                                        else:
                                            cd = row[10]
                                            cd = str(datetime.strptime(
                                                cd, DEFAULT_SERVER_DATE_FORMAT).date())
                                            vals.update({"date_planned": cd})

                                        vals.update(
                                            {'order_id': created_po.id})

                                        line = pol_obj.create(vals)
                                        counter = counter + 1

                                        if self.sh_import_po_unit_price == 'pricelist':
                                            line._product_id_change()
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Product not found. "
                                        counter = counter + 1
                                        if created_po.id in created_po_list_for_confirm:
                                            created_po_list_for_confirm.remove(
                                                created_po.id)
                                        continue

                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Purchase Order not created. "
                                    counter = counter + 1
                                    continue

                            else:
                                skipped_line_no[str(
                                    counter)] = " - Purchase Order or Product field is empty. "
                                counter = counter + 1
                            imported_lines += 1
                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid. " + ustr(e)
                            counter = counter + 1
                            continue
                    # if created_po_list_for_confirm and self.sh_import_po_is_confirm_order:
                    #     purchase_orders = purchase_order_obj.search(
                    #         [('id', 'in', created_po_list_for_confirm)])
                    #     if purchase_orders:
                    #         for purchase_order in purchase_orders:
                    #             purchase_order.button_confirm()
                    # else:
                    #     created_po_list_for_confirm = []
                except Exception as e:
                    raise UserError(
                        _("Sorry, Your csv or excel file does not match with our format"
                        + ustr(e)))
                # if length_reader == self.total_done_po:
                if counter > 1:
                    # if not skipped_line_no:
                    #     self.create_po_logs(
                    #         self.total_done_po, skipped_line_no,0)
                    #     self.state = 'done'
                    completed_records = len(created_po_list)
                    confirm_records = len(created_po_list_for_confirm)
                    if not skipped_line_no:
                        self.create_po_logs(
                            completed_records, skipped_line_no,imported_lines)
                        # if self.received_error:
                        #     self.state = 'partial_done'
                        # else:
                        self.state = 'done' if length_reader == self.total_done_po else 'running'
                    else:
                        self.received_error = True
                        self.create_po_logs(
                            completed_records, skipped_line_no,imported_lines)
                        if self.on_error == 'break':
                            self.state = 'error'
                        elif self.import_limit == 0:
                            if self.received_error:
                                self.state = 'partial_done'
                            else:
                                self.state = 'done' if length_reader == self.total_done_po else None
