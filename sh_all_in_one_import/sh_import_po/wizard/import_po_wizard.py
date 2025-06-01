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


class ImportPOWizard(models.TransientModel):
    _name = "import.po.wizard"
    _description = "Import Purchase Order Wizard"

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
    is_create_vendor = fields.Boolean(string="Create Vendor?")
    is_confirm_order = fields.Boolean(string="Auto Confirm Order?")
    order_no_type = fields.Selection([
        ('auto', 'Auto'),
        ('as_per_sheet', 'As per sheet')
    ], default="auto", string="Reference Number", required=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=default_company)
    unit_price = fields.Selection([
        ('sheet', 'Based on Sheet'),
        ('pricelist', 'Based on Pricelist'),
    ], default="sheet", string="Unit Price", required=True)
    sh_partner_by = fields.Selection([
        ('name', 'Name'),
        ('ref', 'Reference'),
        ('id', 'ID')
    ], default="name", string="Vendor By")

    def show_success_msg(self, imported_lines, failed_lines, skipped_line_no):
        # open the new success message box
        view = self.env.ref('sh_message.sh_message_wizard')
        context = dict(self._context or {})
        dic_msg = str(imported_lines) + " Lines imported successfully \n"
        dic_msg += str(failed_lines) + " Failed to import Lines"
        if skipped_line_no:
          dic_msg += "\nNote:"
        for k, v in skipped_line_no.items():
            dic_msg += "\nLine No " + k + ": " + v

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
                            'row': rowx,
                            'col': colx,
                            'cell_value': xlrd.error_text_from_code.get(
                                cell.value,
                                _("unknown error code %s") % cell.value)
                        })
                else:
                    values.append(cell.value)
            values_sheet.append(values)
        return values_sheet

    def import_po_apply(self):
        ''' .............. Perform to import Purchase Order ...............'''
        pol_obj = self.env['purchase.order.line']
        purchase_order_obj = self.env['purchase.order']
        if self and self.file:
            if self.import_type in ['csv', 'excel']:
                line_counter = 1
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
                    running_po = None
                    created_po = False
                    created_po_list_for_confirm = []
                    created_po_list = []
                    
                    for row in values:
                        try:
                            if skip_header:
                                skip_header = False
                                line_counter += 1
                                continue

                            if row[0] not in (None, "") and row[4] not in (None, ""):
                                vals = {}
                                domain = []

                                if row[0] != running_po:
                                    running_po = row[0]
                                    po_vals = {'company_id': self.company_id.id}

                                    if row[1] not in (None, ""):
                                        partner_obj = self.env["res.partner"]

                                        if self.sh_partner_by == 'name':
                                            domain += [('name', '=', row[1])]
                                            vendor_dic = {'name': row[1]}
                                        if self.sh_partner_by == 'ref':
                                            domain += [('ref', '=', row[1])]
                                            vendor_dic = {'ref': row[1], 'name': row[1]}
                                        if self.sh_partner_by == 'id':
                                            domain += [('id', '=', row[1])]
                                            vendor_dic = {'id': row[1], 'name': row[1]}

                                        partner = partner_obj.search(domain, limit=1)

                                        if partner:
                                            po_vals.update({'partner_id': partner.id})
                                        elif self.is_create_vendor:
                                            vendor_dic.update({'company_type': 'person',
                                                               'supplier_rank': 1,
                                                               'customer_rank': 0})
                                            partner = partner_obj.create(vendor_dic)

                                            if not partner:
                                                skipped_line_no[str(line_counter)] = " - Vendor not created."
                                                line_counter += 1
                                                continue
                                            else:
                                                po_vals.update({'partner_id': partner.id})
                                        else:
                                            skipped_line_no[str(line_counter)] = " - Vendor not found."
                                            line_counter += 1
                                            continue
                                    else:
                                        skipped_line_no[str(line_counter)] = " - Vendor field is empty."
                                        line_counter += 1
                                        continue

                                    if row[2] not in (None, ""):
                                        cd = row[2]
                                        cd = str(datetime.strptime(cd, '%Y-%m-%d').date())
                                        po_vals.update({'date_order': cd})
                                    else:
                                        po_vals.update({'date_order': datetime.now()})

                                    if row[3] not in (None, ""):
                                        cd = row[3]
                                        cd = str(datetime.strptime(cd, '%Y-%m-%d').date())
                                        po_vals.update({'date_planned': cd})

                                    if self.order_no_type == 'as_per_sheet':
                                        po_vals.update({"name": row[0]})
                                    
                                    created_po = purchase_order_obj.create(po_vals)
                                    created_po_list_for_confirm.append(created_po.id)
                                    created_po_list.append(created_po.id)

                                if created_po:
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
                                        vals.update({'product_id': search_product.id})

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
                                            vals.update({'name': search_product.name})

                                        if row[6] != '':
                                            vals.update({'product_qty': row[6]})
                                        else:
                                            vals.update({'product_qty': 1})

                                        if row[7] in (None, "") and search_product.uom_po_id:
                                            vals.update({'product_uom': search_product.uom_po_id.id})
                                        else:
                                            search_uom = self.env['uom.uom'].search(
                                                [('name', '=', row[7])], limit=1)
                                            if search_uom:
                                                vals.update({'product_uom': search_uom.id})
                                            else:
                                                skipped_line_no[str(line_counter)] = " - Unit of Measure not found."
                                                line_counter += 1
                                                if created_po.id in created_po_list_for_confirm:
                                                    created_po_list_for_confirm.remove(created_po.id)
                                                continue

                                        if row[8] in (None, ""):
                                            vals.update({'price_unit': search_product.standard_price})
                                        else:
                                            vals.update({'price_unit': row[8]})

                                        if row[9].strip() in (None, "") and search_product.supplier_taxes_id:
                                            vals.update({'taxes_id': [(6, 0, search_product.supplier_taxes_id.ids)]})
                                        else:
                                            taxes_list = []
                                            some_taxes_not_found = False
                                            for x in row[9].split(','):
                                                x = x.strip()
                                                if x != '':
                                                    search_tax = self.env['account.tax'].search(
                                                        [('name', '=', x)], limit=1)
                                                    if search_tax:
                                                        taxes_list.append(search_tax.id)
                                                    else:
                                                        some_taxes_not_found = True
                                                        skipped_line_no[str(line_counter)] = " - Taxes " + x + " not found."
                                                        break
                                            if some_taxes_not_found:
                                                line_counter += 1
                                                if created_po.id in created_po_list_for_confirm:
                                                    created_po_list_for_confirm.remove(created_po.id)
                                                continue
                                            else:
                                                vals.update({'taxes_id': [(6, 0, taxes_list)]})

                                        if row[10] in (None, ""):
                                            vals.update({'date_planned': datetime.now()})
                                        else:
                                            cd = row[10]
                                            cd = str(datetime.strptime(cd, '%Y-%m-%d').date())
                                            vals.update({"date_planned": cd})

                                        vals.update({'order_id': created_po.id})

                                        line = pol_obj.create(vals)
                                        line_counter += 1

                                        if self.unit_price == 'pricelist':
                                            line._product_id_change()
                                    else:
                                        skipped_line_no[str(line_counter)] = " - Product not found."
                                        line_counter += 1
                                        if created_po.id in created_po_list_for_confirm:
                                            created_po_list_for_confirm.remove(created_po.id)
                                        continue

                                else:
                                    skipped_line_no[str(line_counter)] = " - Purchase Order not created."
                                    line_counter += 1
                                    continue

                            else:
                                skipped_line_no[str(line_counter)] = " - Purchase Order or Product field is empty."
                                line_counter += 1

                        except Exception as e:
                            skipped_line_no[str(line_counter)] = " - Value is not valid: " + ustr(e)
                            line_counter += 1
                            continue

                    if created_po_list_for_confirm and self.is_confirm_order:
                        purchase_orders = purchase_order_obj.search(
                            [('id', 'in', created_po_list_for_confirm)])
                        if purchase_orders:
                            for purchase_order in purchase_orders:
                                purchase_order.button_confirm()
                    else:
                        created_po_list_for_confirm = []

                except Exception as e:
                    raise UserError(
                        _("Sorry, Your file does not match with our format: " + ustr(e)))
                if line_counter > 1:
                    imported_lines = len(created_po_list)
                    failed_lines = line_counter - imported_lines - 1
                    res = self.show_success_msg(imported_lines, failed_lines, skipped_line_no)
                    return res
