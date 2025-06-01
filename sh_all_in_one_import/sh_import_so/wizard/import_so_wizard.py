# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, api, _
from datetime import datetime
from odoo.exceptions import UserError
import csv
import base64
import xlrd
from odoo.tools import ustr
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class ImportSOWizard(models.TransientModel):
    _name = "import.so.wizard"
    _description = "Import Sale Order Wizard"

    @api.model
    def default_company(self):
        return self.env.company

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
    is_create_customer = fields.Boolean(string="Create Customer?")
    is_confirm_sale = fields.Boolean(string="Auto Confirm Sale?")
    order_no_type = fields.Selection([
        ('auto', 'Auto'),
        ('as_per_sheet', 'As per sheet')
    ], default="auto", string="Quotation/Order Number", required=True)
    company_id = fields.Many2one(
        'res.company', 'Company', default=default_company, required=True)
    unit_price = fields.Selection([
        ('sheet', 'Based on Sheet'),
        ('pricelist', 'Based on Pricelist'),
    ], default="sheet", string="Unit Price", required=True)
    sh_partner_by = fields.Selection([
        ('name', 'Name'),
        ('ref', 'Reference'),
        ('id', 'ID')
    ], default="name", string="Customer By")

    def show_success_msg(self, counter, confirm_rec, skipped_line_no):
        # open the new success message box
        view = self.env.ref('sh_message.sh_message_wizard')
        context = dict(self._context or {})
        dic_msg = str(counter) + " Records imported successfully \n"
        dic_msg = dic_msg + str(confirm_rec) + " Records Confirm"
        if skipped_line_no:
            dic_msg = dic_msg + "\nNote:"
        for k, v in skipped_line_no.items():
            dic_msg = dic_msg + "\nRow No " + k + " " + v + " "
        context['message'] = dic_msg

        return {
            'name': 'Success',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
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

    def import_so_apply(self):
        ''' .......... Import Sale Order Using CSV and Excel ..........'''

        sol_obj = self.env['sale.order.line']
        sale_order_obj = self.env['sale.order']
        if self:
            for rec in self:
                if self.import_type == 'csv' or self.import_type == 'excel':
                    counter = 1
                    skipped_line_no = {}
                    try:
                        values = []
                        if self.import_type == 'csv':
                            file = str(
                                base64.decodebytes(self.file).decode('utf-8'))
                            values = csv.reader(file.splitlines())

                        elif self.import_type == 'excel':
                            values = self.read_xls_book()
                        skip_header = True
                        running_so = None
                        created_so = False
                        created_so_list_for_confirm = []
                        created_so_list = []
                        order_date=None
                        for row in values:                            
                            try:
                                if skip_header:
                                    skip_header = False
                                    counter = counter + 1
                                    continue
                                if row[0] not in (None, "") and row[4] not in (None, ""):
                                    vals = {}
                                    domain = []

                                    if row[0] != running_so:

                                        running_so = row[0]
                                        so_vals = {
                                            'company_id': rec.company_id.id}

                                        if row[1] not in (None, ""):
                                            partner_obj = self.env["res.partner"]
                                            if self.sh_partner_by == 'name':
                                                domain += [('name',
                                                            '=', row[1])]
                                                customer_dic = {'name': row[1]}
                                            if self.sh_partner_by == 'ref':
                                                domain += [('ref',
                                                            '=', row[1])]
                                                customer_dic = {
                                                    'ref': row[1], 'name': row[1]}
                                            if self.sh_partner_by == 'id':
                                                domain += [('id', '=', row[1])]
                                                customer_dic = {
                                                    'id': row[1], 'name': row[1]}

                                            partner = partner_obj.search(
                                                domain, limit=1)

                                            if partner:
                                                so_vals.update(
                                                    {'partner_id': partner.id})
                                            elif rec.is_create_customer:
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
                                                cd, '%Y-%m-%d').date())
                                            order_date=None
                                            order_date = cd                                            
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

                                        if rec.order_no_type == 'as_per_sheet':
                                            so_vals.update({"name": row[0]})
                                        created_so = sale_order_obj.create(
                                            so_vals)                                        
                                        created_so_list_for_confirm.append(
                                            created_so.id)
                                        created_so_list.append(created_so.id)
                                    if created_so:
                                        field_nm = 'name'
                                        if rec.product_by == 'name':
                                            field_nm = 'name'
                                        elif rec.product_by == 'int_ref':
                                            field_nm = 'default_code'
                                        elif rec.product_by == 'barcode':
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

                                            if self.unit_price == 'pricelist':
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

                            except Exception as e:
                                skipped_line_no[str(
                                    counter)] = " - Value is not valid " + ustr(e)
                                counter = counter + 1
                                continue
                        if created_so_list_for_confirm and rec.is_confirm_sale:
                            sale_orders = sale_order_obj.search(
                                [('id', 'in', created_so_list_for_confirm)])
                            if sale_orders:
                                for sale_order in sale_orders:
                                    sale_order.action_confirm()                                      
                                    if order_date:                                      
                                        sale_order.sudo().write({'date_order': order_date})                                        
                        else:
                            created_so_list_for_confirm = []

                    except Exception as e:
                        raise UserError(
                            _("Sorry, Your file does not match with our format " + ustr(e)))

                    if counter > 1:
                        completed_records = len(created_so_list)
                        confirm_rec = len(created_so_list_for_confirm)
                        res = self.show_success_msg(
                            completed_records, confirm_rec, skipped_line_no)
                        return res
