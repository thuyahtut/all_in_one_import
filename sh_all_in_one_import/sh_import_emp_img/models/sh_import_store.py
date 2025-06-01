# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _
from odoo.exceptions import UserError
import csv
import base64
from odoo.tools import ustr
import requests
import codecs


class ImportStore(models.Model):
    _inherit = "sh.import.store"

    def check_sh_import_emp_img(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_emp_img':
            value = True
        return value

    import_emp_img_type = fields.Selection(related='base_id.import_emp_img_type',readonly=False, string="Import File Type")
    emp_by = fields.Selection(related='base_id.emp_by',readonly=False, string="Employee By")
    sh_import_emp_img_boolean = fields.Boolean(
        "Import Emp Img Boolean", default=check_sh_import_emp_img)

    def perform_the_action(self, record):
        res = super(ImportStore, self).perform_the_action(record)
        if record.base_id.sh_technical_name == 'sh_import_emp_img':
            self.import_emp_img(record)
        return res

    def import_emp_img(self,record):
        self = record
        hr_emp_obj = self.env['hr.employee']
        # # perform import EMP Image
        if self and self.sh_file:

            if self.import_emp_img_type == 'csv' or self.import_emp_img_type == 'excel':
                counter = 1
                skipped_line_no = {}
                count=0
                try:
                    if self.import_emp_img_type == 'csv':
                        sh_file = str(base64.decodebytes(
                            self.sh_file).decode('utf-8'))
                        length_r = csv.reader(sh_file.splitlines())
                        length_reader = len(list(length_r))
                        myreader = csv.reader(sh_file.splitlines())
                        myreader = list(myreader)                       
                    elif self.import_emp_img_type == 'excel':
                        myreader=self.read_xls_book()                       
                        length_reader = len(myreader)

                    skip_header = True
                    dic = {}
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
                                if self.emp_by == 'name':
                                    field_nm = 'name'
                                elif self.emp_by == 'db_id':
                                    field_nm = 'id'
                                elif self.emp_by == 'id_no':
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
                                counter)] = " - Value is not valid " + ustr(e)
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
