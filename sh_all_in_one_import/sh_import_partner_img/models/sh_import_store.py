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
import codecs
import requests
import logging
_logger = logging.getLogger(__name__)


class ImportStore(models.Model):
    _inherit = "sh.import.store"

    def check_sh_import_partner_img(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_partner_img':
            value = True
        return value

    sh_import_partner_img_type = fields.Selection(related='base_id.sh_import_partner_img_type',readonly=False, string="Import File Type", required=True)
    sh_import_partner_img_partner_by = fields.Selection(related='base_id.sh_import_partner_img_partner_by',readonly=False, string="Customer By", required=True)
    sh_import_partner_img_boolean = fields.Boolean(
        "Import Partner Image Boolean", default=check_sh_import_partner_img)
    sh_company_id_partner_img = fields.Many2one(
        related="base_id.sh_company_id_partner_img", readonly=False, string="Company", required=True)

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
        if record.base_id.sh_technical_name == 'sh_import_partner_img':
            self.import_partner_img(record)
        return res

    def import_partner_img(self,record):
        self = record
        partner_obj = self.env["res.partner"]

        # # perform import SO
        if self and self.sh_file:

            if self.sh_import_partner_img_type == 'csv' or self.sh_import_partner_img_type == 'excel':
                counter = 1
                skipped_line_no = {}
                count=0
                try:
                    if self.sh_import_partner_img_type == 'csv':
                        sh_file = str(base64.decodebytes(
                            self.sh_file).decode('utf-8'))
                        length_r = csv.reader(sh_file.splitlines())
                        length_reader = len(list(length_r))
                        myreader = csv.reader(sh_file.splitlines())
                        myreader = list(myreader)                       
                    elif self.sh_import_partner_img_type == 'excel':
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
                            if row[0] not in (None, "") and row[1].strip() not in (None, ""):
                                vals = {}
                                image_path = row[1].strip()
                                if "http://" in image_path or "https://" in image_path:
                                    try:
                                        r = requests.get(image_path)
                                        if r and r.content:
                                            image_base64 = base64.encodebytes(
                                                r.content)
                                            vals.update(
                                                {'image_1920': image_base64})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - URL not correct or check your image size. "
                                            counter = counter + 1
                                            continue
                                    except Exception as e:
                                        skipped_line_no[str(
                                            counter)] = " - URL not correct or check your image size " + ustr(e)
                                        counter = counter + 1
                                        continue

                                else:
                                    try:
                                        with open(image_path, 'rb') as image:
                                            image.seek(0)
                                            binary_data = image.read()
                                            image_base64 = codecs.encode(
                                                binary_data, 'base64')
                                            if image_base64:
                                                vals.update(
                                                    {'image_1920': image_base64})
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Could not find the image or please make sure it is accessible to this app. "
                                                counter = counter + 1
                                                continue
                                    except Exception as e:
                                        skipped_line_no[str(
                                            counter)] = " - Could not find the image or please make sure it is accessible to this app. " + ustr(e)
                                        counter = counter + 1
                                        continue

                                field_nm = 'name'
                                if self.sh_import_partner_img_partner_by == 'name':
                                    field_nm = 'name'
                                elif self.sh_import_partner_img_partner_by == 'db_id':
                                    field_nm = 'id'
                                elif self.sh_import_partner_img_partner_by == 'int_ref':
                                    field_nm = 'ref'

                                search_partner = partner_obj.search(
                                    [(field_nm, '=', row[0])], limit=1)
                                if search_partner:
                                    search_partner.write(vals)
                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Customer not found. "

                                counter = counter + 1
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Customer or URL/Path field is empty. "
                                counter = counter + 1
                                continue
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
