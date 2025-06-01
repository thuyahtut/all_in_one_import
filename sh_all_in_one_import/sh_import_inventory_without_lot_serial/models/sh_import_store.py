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
import logging
_logger = logging.getLogger(__name__)


class ImportStore(models.Model):
    _inherit = "sh.import.store"

    def check_sh_import_without_lot_serial(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_inventory_without_lot_serial':
            value = True
        return value

    sh_import_without_lot_serial_type = fields.Selection(related='base_id.sh_import_without_lot_serial_type',readonly=False, string="Import File Type")

    sh_import_without_lot_serial_product_by = fields.Selection(related='base_id.sh_import_without_lot_serial_product_by',readonly=False, string="Product By")

    sh_import_without_lot_serial_location_id = fields.Many2one("stock.location", string="Location",related='base_id.sh_import_without_lot_serial_location_id',readonly=False)
    sh_import_without_lot_serial_name = fields.Char(related='base_id.sh_import_without_lot_serial_name',readonly=False,string="Inventory Reference")
    sh_import_without_lot_serial_boolean = fields.Boolean(
        "Import Without Lot-Serial Boolean", default=check_sh_import_without_lot_serial)
    sh_company_id_without_lot_serial = fields.Many2one(
        related="base_id.sh_company_id_without_lot_serial", readonly=False, string="Company", required=True)

    def create_store_logs(self, counter, skipped_line_no):
        dic_msg = str(counter) + " Records imported successfully"
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
        if record.base_id.sh_technical_name == 'sh_import_inventory_without_lot_serial':
            self.import_without_lot_serial(record)
        return res

    def import_without_lot_serial(self,record):
        self = record

        # # perform import Inventory
        if self and self.sh_file and self.sh_import_without_lot_serial_location_id:

            if self.sh_import_without_lot_serial_type == 'csv' or self.sh_import_without_lot_serial_type == 'excel':
                counter = 1
                skipped_line_no = {}
                count=0
                try:
                    if self.sh_import_without_lot_serial_type == 'csv':
                        sh_file = str(base64.decodebytes(
                            self.sh_file).decode('utf-8'))
                        length_r = csv.reader(sh_file.splitlines())
                        length_reader = len(list(length_r))
                        myreader = csv.reader(sh_file.splitlines())
                        myreader = list(myreader)                       
                    elif self.sh_import_without_lot_serial_type == 'excel':
                        myreader=self.read_xls_book()                       
                        length_reader = len(myreader)

                    skip_header = True
                    till = length_reader
                    
                    if self.import_limit == 0 or self.count_start_from+self.import_limit > length_reader:
                        till = length_reader
                    else:
                        till = self.count_start_from+self.import_limit
                    for row in range(self.count_start_from - 1, till):
                        try:
                            row = myreader[row] 
                            count += 1 
                            self.current_count += 1                                                       
                            if count == self.import_limit:
                                self.count_start_from += self.import_limit   
                            if skip_header:   
                                skip_header = False
                                continue
                            if row[0] not in (None, ""):
                                field_nm = 'name'
                                if self.sh_import_without_lot_serial_product_by == 'name':
                                    field_nm = 'name'
                                elif self.sh_import_without_lot_serial_product_by == 'int_ref':
                                    field_nm = 'default_code'
                                elif self.sh_import_without_lot_serial_product_by == 'barcode':
                                    field_nm = 'barcode'

                                search_product = self.env['product.product'].search(
                                    [(field_nm, '=', row[0])], limit=1)
                                if search_product and search_product.type == 'product' and search_product.tracking not in ['serial', 'lot']:
                                    quant_id = self.env['stock.quant'].search([('location_id', '=', self.sh_import_without_lot_serial_location_id.id), (
                                        'company_id', '=', self.env.company.id), ('product_id', '=', search_product.id)], limit=1)
                                    quant_vals = {}
                                    if quant_id:
                                        quant_vals.update({
                                            'display_name': self.sh_import_without_lot_serial_name,
                                            'inventory_quantity': float(row[1]),
                                            'product_id': search_product.id,
                                            'location_id': self.sh_import_without_lot_serial_location_id.id
                                        })
                                        quant_id.sudo().write(quant_vals)
                                        quant_id.action_apply_inventory()
                                    else:
                                        quant_vals.update({
                                            'display_name': self.sh_import_without_lot_serial_name,
                                            'product_id': search_product.id,
                                            'product_categ_id': search_product.categ_id.id,
                                            'inventory_date': fields.Date.today(),
                                            'user_id': self.env.user.id,
                                            'location_id': self.sh_import_without_lot_serial_location_id.id
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
                                counter)] = " - Value is not valid. " + ustr(e)
                            counter = counter + 1
                            continue
                except Exception as e:
                    raise UserError(
                        _("Sorry, Your csv or excel file does not match with our format"
                        + ustr(e)))
                if counter > 1:
                    completed_records = (counter - len(skipped_line_no)) - 1
                    if not skipped_line_no:
                        self.create_store_logs(
                            completed_records, skipped_line_no)
                        self.state = 'done'
                    else:
                        self.received_error = True
                        self.create_store_logs(
                            completed_records, skipped_line_no)
                        if self.on_error == 'break':
                            self.state = 'error'
                        elif self.import_limit == 0:
                            if self.received_error:
                                self.state = 'partial_done'
                            else:
                                self.state = 'done'
