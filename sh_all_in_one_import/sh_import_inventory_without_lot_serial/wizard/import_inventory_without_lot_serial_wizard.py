# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
import datetime
from odoo.tools import ustr
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class ImportInventoryWithoutLotSerialWizard(models.TransientModel):
    _name = "import.inventory.without.lot.serial.wizard"
    _description = "Import Inventory Without lot or serial number wizard"

    @api.model
    def _default_location_id(self):
        company_user = self.env.company
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', company_user.id)], limit=1)
        if warehouse:
            return warehouse.lot_stock_id.id
        else:
            raise UserError(
                _('You must define a warehouse for the company: %s.') % (company_user.name,))

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

    location_id = fields.Many2one("stock.location", string="Location",
                                  domain="[('usage','not in', ['supplier','production'])]", required=True, default=_default_location_id)
    name = fields.Char(string="Inventory Reference", required=True)

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

    def import_inventory_without_lot_serial_apply(self):
        ''' ...... import inventory without lot serial number......'''
        if self and self.file and self.location_id:
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
                    for row in values:
                        try:
                            if skip_header:
                                skip_header = False
                                counter = counter + 1
                                continue

                            if row[0] not in (None, ""):
                                field_nm = 'name'
                                if self.product_by == 'name':
                                    field_nm = 'name'
                                elif self.product_by == 'int_ref':
                                    field_nm = 'default_code'
                                elif self.product_by == 'barcode':
                                    field_nm = 'barcode'

                                search_product = self.env['product.product'].search(
                                    [(field_nm, '=', row[0])], limit=1)
                                if search_product and search_product.type == 'product' and search_product.tracking not in ['serial', 'lot']:
                                    quant_id = self.env['stock.quant'].search([('location_id', '=', self.location_id.id), (
                                        'company_id', '=', self.env.company.id), ('product_id', '=', search_product.id)], limit=1)
                                    quant_vals = {}
                                    if quant_id:
                                        quant_vals.update({
                                            'display_name': self.name,
                                            'inventory_quantity': float(row[1]),
                                            'product_id': search_product.id,
                                            'location_id': self.location_id.id
                                        })
                                        quant_id.sudo().write(quant_vals)
                                        quant_id.action_apply_inventory()
                                    else:
                                        quant_vals.update({
                                            'display_name': self.name,
                                            'product_id': search_product.id,
                                            'product_categ_id': search_product.categ_id.id,
                                            'inventory_date': fields.Date.today(),
                                            'user_id': self.env.user.id,
                                            'location_id': self.location_id.id
                                        })
                                        if row[1] not in (None, ""):
                                            quant_vals.update(
                                                {'inventory_quantity': row[1]})
                                        else:
                                            quant_vals.update(
                                                {'inventory_quantity': 0.0})
                                        if row[2].strip() not in (None, ""):
                                            search_uom = self.env['uom.uom'].search(
                                                [('name', '=', row[2].strip())], limit=1)
                                            if search_uom:
                                                quant_vals.update(
                                                    {'product_uom_id': search_uom.id})
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Unit of Measure not found. "
                                                counter = counter + 1
                                                continue
                                        elif search_product.uom_id:
                                            quant_vals.update(
                                                {'product_uom_id': search_product.uom_id.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Unit of Measure not defined for this product. "
                                            counter = counter + 1
                                            continue
                                        quant_id = self.env['stock.quant'].sudo().create(
                                            quant_vals)
                                        # check if stock move line exist or not
                                        if quant_id:
                                            quant_id.action_apply_inventory()
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Inventory could not be created. "
                                            counter = counter + 1
                                            continue
                                    counter = counter + 1
                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Product not found or it's not a Stockable Product or it's traceable by lot/serial number. "
                                    counter = counter + 1
                                    continue
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Product is empty. "
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
                    completed_records = (counter - len(skipped_line_no)) - 2
                    res = self.show_success_msg(
                        completed_records, skipped_line_no)
                    return res
