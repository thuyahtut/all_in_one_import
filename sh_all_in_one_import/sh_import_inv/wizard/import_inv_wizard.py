# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _
from datetime import datetime
from odoo.exceptions import UserError
import csv
import base64
import xlrd
from odoo.tools import ustr
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class ImportINVWizard(models.TransientModel):
    _name = "import.inv.wizard"
    _description = "Import INV"

    import_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    file = fields.Binary(string="File", required=True)
    product_by = fields.Selection([
        ('name', 'Name'),
        ('int_ref', 'Internal Reference'),
        ('barcode', 'Barcode')
    ], default="name", string="Product By", required=True)
    invoice_type = fields.Selection([
        ('inv', 'Customer Invoice'),
        ('bill', 'Vendor Bill'),
        ('ccn', 'Customer Credit Note'),
        ('vcn', 'Vendor Credit Note')
    ], default="inv", string="Invoicing Type", required=True)
    is_validate = fields.Boolean(string="Auto Post?")
    inv_no_type = fields.Selection([
        ('auto', 'Auto'),
        ('as_per_sheet', 'As per sheet')
    ], default="auto", string="Number", required=True)
    account_option = fields.Selection(
        [('default', 'Auto'), ('sheet', 'As per sheet')], default='default', string='Account')
    sh_partner_by = fields.Selection([
        ('name', 'Name'),
        ('ref', 'Reference'),
        ('id', 'ID')
    ], default="name", string="Customer By")

    def show_success_msg(self, counter, validate_rec, skipped_line_no):
        # open the new success message box
        view = self.env.ref('sh_message.sh_message_wizard')
        context = dict(self._context or {})
        dic_msg = str(counter) + " Records imported successfully \n"
        dic_msg = dic_msg + str(validate_rec) + " Records Validate"
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

    def import_inv_apply(self):
        inv_obj = self.env['account.move']
        # perform import lead
        if self and self.file:
            # For CSV
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
                    running_inv = None
                    created_inv = False
                    created_inv_list_for_validate = []
                    created_inv_list = []

                    for row in values:
                        try:
                            if skip_header:
                                skip_header = False
                                counter = counter + 1
                                continue

                            if row[0] not in (None, "") and row[4] not in (None, ""):
                                vals = {}
                                if row[0] != running_inv:

                                    running_inv = row[0]
                                    inv_vals = {}
                                    domain = []

                                    if row[1] not in (None, ""):
                                        partner_obj = self.env["res.partner"]

                                        if self.sh_partner_by == 'name':
                                            domain += [('name', '=', row[1])]
                                        if self.sh_partner_by == 'ref':
                                            domain += [('ref', '=', row[1])]
                                        if self.sh_partner_by == 'id':
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
                                            cd, '%Y-%m-%d').date())
                                        inv_vals.update({'invoice_date': cd})
                                    if self.inv_no_type == 'as_per_sheet':
                                        inv_vals.update({"name": row[0]})
                                    created_inv = False
                                    if self.invoice_type == 'inv':
                                        inv_vals.update(
                                            {"move_type": "out_invoice"})
                                        created_inv = inv_obj.with_context(
                                            default_move_type='out_invoice').create(inv_vals)
                                    elif self.invoice_type == 'bill':
                                        inv_vals.update(
                                            {"move_type": "in_invoice"})
                                        created_inv = inv_obj.with_context(
                                            default_move_type='in_invoice').create(inv_vals)
                                    elif self.invoice_type == 'ccn':
                                        inv_vals.update(
                                            {"move_type": "out_refund"})
                                        created_inv = inv_obj.with_context(
                                            default_move_type='out_refund').create(inv_vals)
                                    elif self.invoice_type == 'vcn':
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
                                    if self.product_by == 'name':
                                        field_nm = 'name'
                                    elif self.product_by == 'int_ref':
                                        field_nm = 'default_code'
                                    elif self.product_by == 'barcode':
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
                                        if self.account_option == 'default':
                                            accounts = search_product.product_tmpl_id.get_product_accounts(
                                                created_inv.fiscal_position_id)
                                            if created_inv.move_type in ('out_invoice', 'out_refund'):
                                                account = accounts['income']
                                            else:
                                                account = accounts['expense']
                                        elif self.account_option == 'sheet' and row[3] not in ("", None):
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
                                    invoice_line_ids = []

                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Order not created. "
                                    counter = counter + 1
                                    continue

                            else:
                                skipped_line_no[str(
                                    counter)] = " - Number or Product field is empty. "
                                counter = counter + 1

                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid " + ustr(e)
                            counter = counter + 1
                            continue

#                   here call necessary method
                    if created_inv_list:
                        invoices = inv_obj.search(
                            [('id', 'in', created_inv_list)])
                        if invoices:
                            for invoice in invoices:
                                invoice._onchange_partner_id()
#                     validate invoice
                    if created_inv_list_for_validate and self.is_validate:
                        invoices = inv_obj.search(
                            [('id', 'in', created_inv_list_for_validate)])
                        if invoices:
                            for invoice in invoices:
                                invoice.action_post()
                                if self.inv_no_type == 'auto':
                                    invoice._compute_name()
                                else:
                                    invoice.write({"name": row[0]})
                    else:
                        created_inv_list_for_validate = []
                except Exception as e:
                    raise UserError(
                        _("Sorry, Your file does not match with our format" + ustr(e)))

                if counter > 1:
                    completed_records = len(created_inv_list)
                    validate_rec = len(created_inv_list_for_validate)
                    res = self.show_success_msg(
                        completed_records, validate_rec, skipped_line_no)
                    return res
