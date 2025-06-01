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

    def check_sh_import_inv(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_inv':
            value = True
        return value

    sh_import_inv_type = fields.Selection(related='base_id.sh_import_inv_type',readonly=False, string="Import File Type")
    sh_import_inv_product_by = fields.Selection(related='base_id.sh_import_inv_product_by',readonly=False, string="Product By")
    sh_import_inv_invoice_type = fields.Selection(related='base_id.sh_import_inv_invoice_type',readonly=False, string="Invoicing Type")
    sh_import_inv_is_validate = fields.Boolean(related='base_id.sh_import_inv_is_validate',readonly=False,string="Auto Post?")
    sh_import_inv_inv_no_type = fields.Selection(related='base_id.sh_import_inv_inv_no_type',readonly=False, string="Number")
    sh_import_inv_account_option = fields.Selection(related='base_id.sh_import_inv_account_option',readonly=False, string='Account')
    sh_import_inv_partner_by = fields.Selection(related='base_id.sh_import_inv_partner_by',readonly=False, string="Customer By")
    sh_import_inv_boolean = fields.Boolean(
        "Import Invoice Boolean", default=check_sh_import_inv)
    sh_company_id_inv = fields.Many2one(
        related="base_id.sh_company_id_inv", readonly=False, string="Company", required=True)
    running_inv = fields.Char(string='Running Inv')
    total_done_inv = fields.Integer("Total Done Inv")

    def create_inv_logs(self, counter, skipped_line_no,confirm_records):
        # dic_msg = str(counter) + " Records imported successfully"+"\n"
        # dic_msg = dic_msg + str(confirm_records) + " Records Validate"
        # if confirm_records:
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
        if record.base_id.sh_technical_name == 'sh_import_inv':
            self.import_inv(record)
        return res

    def import_inv(self,record):
        self = record
        inv_obj = self.env['account.move']
        # # perform import Invoice
        if self and self.sh_file:
            if self.sh_import_inv_type == 'csv' or self.sh_import_inv_type == 'excel':
                counter = 1
                skipped_line_no = {}
                count=0
                self.running_inv = None
                created_inv = False
                created_inv_list_for_validate = []
                created_inv_list = []
                imported_lines = 0
                try:
                    if self.sh_import_inv_type == 'csv':
                        sh_file = str(base64.decodebytes(
                            self.sh_file).decode('utf-8'))
                        length_r = csv.reader(sh_file.splitlines())
                        length_reader = len(list(length_r))
                        myreader = csv.reader(sh_file.splitlines())
                        myreader = list(myreader)                       
                    elif self.sh_import_inv_type == 'excel':
                        myreader=self.read_xls_book()                       
                        length_reader = len(myreader)

                    skip_header = True
                    till = length_reader                    

                    if self.import_limit == 0 or self.count_start_from+self.import_limit > length_reader:
                        till = length_reader
                    else:
                        till = self.count_start_from+self.import_limit

                    self.total_done_inv = till                       
                    for row in range(self.count_start_from - 1, till):
                        try:
                            created_inv = self.env['account.move'].sudo().search([('name','=',self.running_inv)],limit=1)
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
                                if row[0] != self.running_inv:

                                    self.running_inv = row[0]
                                    inv_vals = {}
                                    domain = []

                                    if row[1] not in (None, ""):
                                        partner_obj = self.env["res.partner"]

                                        if self.sh_import_inv_partner_by == 'name':
                                            domain += [('name', '=', row[1])]
                                        if self.sh_import_inv_partner_by == 'ref':
                                            domain += [('ref', '=', row[1])]
                                        if self.sh_import_inv_partner_by == 'id':
                                            domain += [('id', '=', row[1])]

                                        partner = partner_obj.search(
                                            domain, limit=1)

                                        if partner:
                                            inv_vals.update(
                                                {'partner_id': partner.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Customer/Vendor not found. "
                                            counter = counter + 1
                                            continue
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Customer/Vendor field is empty. "
                                        counter = counter + 1
                                        continue

                                    if row[2] not in (None, ""):
                                        cd = row[2]
                                        cd = str(datetime.strptime(
                                            cd, DEFAULT_SERVER_DATE_FORMAT).date())
                                        inv_vals.update({'invoice_date': cd})
                                    if self.sh_import_inv_inv_no_type == 'as_per_sheet':
                                        inv_vals.update({"name": row[0]})
                                    # created_inv = False
                                    if self.sh_import_inv_invoice_type == 'inv':
                                        inv_vals.update(
                                            {"move_type": "out_invoice"})
                                        created_inv = inv_obj.with_context(
                                            default_move_type='out_invoice').create(inv_vals)
                                        created_inv._compute_name()
                                    elif self.sh_import_inv_invoice_type == 'bill':
                                        inv_vals.update(
                                            {"move_type": "in_invoice"})
                                        created_inv = inv_obj.with_context(
                                            default_move_type='in_invoice').create(inv_vals)
                                    elif self.sh_import_inv_invoice_type == 'ccn':
                                        inv_vals.update(
                                            {"move_type": "out_refund"})
                                        created_inv = inv_obj.with_context(
                                            default_move_type='out_refund').create(inv_vals)
                                    elif self.sh_import_inv_invoice_type == 'vcn':
                                        inv_vals.update(
                                            {"move_type": "in_refund"})
                                        created_inv = inv_obj.with_context(
                                            default_move_type='in_refund').create(inv_vals)

                                    invoice_line_ids = []
                                    created_inv_list_for_validate.append(
                                        created_inv.id)
                                    created_inv_list.append(created_inv.id)

                                if created_inv:

                                    field_nm = 'name'
                                    if self.sh_import_inv_product_by == 'name':
                                        field_nm = 'name'
                                    elif self.sh_import_inv_product_by == 'int_ref':
                                        field_nm = 'default_code'
                                    elif self.sh_import_inv_product_by == 'barcode':
                                        field_nm = 'barcode'

                                    search_product = self.env['product.product'].search(
                                        [(field_nm, '=', row[4])], limit=1)
                                    if search_product:
                                        vals.update(
                                            {'product_id': search_product.id})

                                        if row[5] != '':
                                            vals.update({'name': row[5]})
                                        else:
                                            product = None
                                            name = ''
                                            if created_inv.partner_id:
                                                if created_inv.partner_id.lang:
                                                    product = search_product.with_context(
                                                        lang=created_inv.partner_id.lang)
                                                else:
                                                    product = search_product

                                                name = product.partner_ref
                                            if created_inv.move_type in ('in_invoice', 'in_refund') and product:
                                                if product.description_purchase:
                                                    name += '\n' + product.description_purchase
                                            elif product:
                                                if product.description_sale:
                                                    name += '\n' + product.description_sale
                                            vals.update({'name': name})
                                        account = False
                                        if self.sh_import_inv_account_option == 'default':
                                            accounts = search_product.product_tmpl_id.get_product_accounts(
                                                created_inv.fiscal_position_id)
                                            if created_inv.move_type in ('out_invoice', 'out_refund'):
                                                account = accounts['income']
                                            else:
                                                account = accounts['expense']
                                        elif self.sh_import_inv_account_option == 'sheet' and row[3] not in ("", None):
                                            account_id = self.env['account.account'].sudo().search(
                                                [('code', '=', row[3])], limit=1)
                                            if account_id:
                                                account = account_id
                                        if not account:
                                            skipped_line_no[str(
                                                counter)] = " - Account not found. "
                                            counter = counter + 1
                                            if created_inv.id in created_inv_list_for_validate:
                                                created_inv_list_for_validate.remove(
                                                    created_inv.id)
                                            continue
                                        else:
                                            vals.update(
                                                {'account_id': account.id})
                                        if row[6] != '':
                                            vals.update({'quantity': row[6]})
                                        else:
                                            vals.update({'quantity': 1})

                                        if row[7] in (None, ""):
                                            if created_inv.move_type in ('in_invoice', 'in_refund') and search_product.uom_po_id:
                                                vals.update(
                                                    {'product_uom_id': search_product.uom_po_id.id})
                                            elif search_product.uom_id:
                                                vals.update(
                                                    {'product_uom_id': search_product.uom_id.id})
                                        else:
                                            search_uom = self.env['uom.uom'].search(
                                                [('name', '=', row[7])], limit=1)
                                            if search_uom:
                                                vals.update(
                                                    {'product_uom_id': search_uom.id})
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Unit of Measure not found. "
                                                counter = counter + 1
                                                if created_inv.id in created_inv_list_for_validate:
                                                    created_inv_list_for_validate.remove(
                                                        created_inv.id)
                                                continue

                                        if row[8] in (None, ""):
                                            if created_inv.move_type in ('in_invoice', 'in_refund'):
                                                vals.update(
                                                    {'price_unit': search_product.standard_price})
                                            else:
                                                vals.update(
                                                    {'price_unit': search_product.lst_price})
                                        else:
                                            vals.update({'price_unit': row[8]})

                                        if row[9].strip() in (None, ""):
                                            if created_inv.move_type in ('in_invoice', 'in_refund') and search_product.supplier_taxes_id:
                                                vals.update(
                                                    {'tax_ids': [(6, 0, search_product.supplier_taxes_id.ids)]})
                                            elif created_inv.move_type in ('out_invoice', 'out_refund') and search_product.taxes_id:
                                                vals.update(
                                                    {'tax_ids': [(6, 0, search_product.taxes_id.ids)]})

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
                                                if created_inv.id in created_inv_list_for_validate:
                                                    created_inv_list_for_validate.remove(
                                                        created_inv.id)
                                                continue
                                            else:
                                                vals.update(
                                                    {'tax_ids': [(6, 0, taxes_list)]})

                                        vals.update(
                                            {'move_id': created_inv.id})
                                        invoice_line_ids.append((0, 0, vals))
                                        vals = {}
                                        counter = counter + 1

                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Product not found. "
                                        counter = counter + 1
                                        if created_inv.id in created_inv_list_for_validate:
                                            created_inv_list_for_validate.remove(
                                                created_inv.id)
                                        continue
                                    created_inv.write(
                                        {'invoice_line_ids': invoice_line_ids})
                                    

                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Order not created. "
                                    counter = counter + 1
                                    continue

                            else:
                                skipped_line_no[str(
                                    counter)] = " - Number or Product field is empty. "
                                counter = counter + 1
                            imported_lines += 1    
                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid. " + ustr(e)
                            counter = counter + 1
                            continue

                    # Here call necessary method
                    if created_inv_list:
                        invoices = inv_obj.search(
                            [('id', 'in', created_inv_list)])
                        if invoices:
                            for invoice in invoices:
                                invoice._onchange_partner_id()
                    # Validate invoice
                    # if created_inv_list_for_validate and self.sh_import_inv_is_validate:
                    #     invoices = inv_obj.search(
                    #         [('id', 'in', created_inv_list_for_validate)])
                    #     if invoices:
                    #         for invoice in invoices:
                    #             invoice.action_post()
                    # else:
                    #     created_inv_list_for_validate = []
                except Exception as e:
                    raise UserError(
                        _("Sorry, Your csv or excel file does not match with our format"
                        + ustr(e)))
                
                
                if counter > 1:
                    # if not skipped_line_no:
                    #     self.create_inv_logs(
                    #         self.total_done_inv, skipped_line_no,0)
                    #     self.state = 'done'
                    completed_records = len(created_inv_list)
                    confirm_records = len(created_inv_list_for_validate)
                    if not skipped_line_no:
                        self.create_inv_logs(
                            completed_records, skipped_line_no,imported_lines)
                        if self.received_error:
                            self.state = 'partial_done'
                        else:
                            self.state = 'done' if length_reader == self.total_done_inv else 'running'
                    else:
                        self.received_error = True
                        self.create_inv_logs(
                            completed_records, skipped_line_no,imported_lines)
                        if self.on_error == 'break':
                            self.state = 'error'
                        elif self.import_limit == 0:
                            if self.received_error:
                                self.state = 'partial_done'
                            else:
                                self.state = 'done' if length_reader == self.total_done_inv else None

                    # if not skipped_line_no:
                    #     self.create_inv_logs(
                    #         completed_records, skipped_line_no,imported_lines)
                    #     self.state = 'done'
                    # else:
                    #     self.received_error = True
                    #     self.create_inv_logs(
                    #         completed_records, skipped_line_no,imported_lines)
                    #     if self.on_error == 'break':
                    #         self.state = 'error'
                    #     elif self.import_limit == 0:
                    #         if self.received_error:
                    #             self.state = 'partial_done'
                    #         else:
                    #             self.state = 'done'
