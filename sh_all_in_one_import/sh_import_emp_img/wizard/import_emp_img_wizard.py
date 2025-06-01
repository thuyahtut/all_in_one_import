# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
from odoo.tools import ustr
import requests
import codecs
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class ImportEmpImgWizard(models.TransientModel):
    _name = "import.emp.img.wizard"
    _description = "Import Employee Image Wizard"

    import_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    file = fields.Binary(string="File", required=True)
    emp_by = fields.Selection([
        ('name', 'Name'),
        ('db_id', 'ID'),
        ('id_no', 'Identification No')
    ], default="name", string="Employee By", required=True)

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

    def import_emp_img_apply(self):
        ''' .......... Import employee Image Using CSV and EXCEL ........... '''
        hr_emp_obj = self.env['hr.employee']
        if self and self.file:
            if self.import_type == 'csv' or self.import_type == 'excel':
                for rec in self:
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
                                    if rec.emp_by == 'name':
                                        field_nm = 'name'
                                    elif rec.emp_by == 'db_id':
                                        field_nm = 'id'
                                    elif rec.emp_by == 'id_no':
                                        field_nm = 'identification_id'

                                    search_emp = hr_emp_obj.search(
                                        [(field_nm, '=', row[0])], limit=1)
                                    if search_emp:
                                        search_emp.write(vals)
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Employee not found. "

                                    counter = counter + 1
                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Employee or URL/Path field is empty. "
                                    counter = counter + 1
                                    continue

                            except Exception as e:
                                skipped_line_no[str(
                                    counter)] = " - Value is not valid. " + ustr(e)
                                counter = counter + 1
                                continue

                    except Exception as e:
                        raise UserError(
                            _("Sorry, Your file does not match with our format " + ustr(e)))

                    if counter > 1:
                        completed_records = (
                            counter - len(skipped_line_no)) - 2
                        res = rec.show_success_msg(
                            completed_records, skipped_line_no)
                        return res
