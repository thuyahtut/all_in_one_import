# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from operator import length_hint
from odoo import fields, models, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
from datetime import datetime
from odoo.tools import ustr
import requests
import codecs


class ImportProductImage(models.Model):
    _inherit = "sh.import.store"

    def check_sh_import_product_img(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_product_img':
            value = True
        return value

    import_type = fields.Selection(
        related="base_id.import_type", readonly=False, string="Import File Type", required=True)
    product_by = fields.Selection(
        related="base_id.product_by", readonly=False, string="Product By", required=True)
    product_model = fields.Selection(
        related="base_id.product_model", readonly=False, string="Product Model", required=True)
    sh_import_product_img_boolean = fields.Boolean(
        "Product Image Boolean", default=check_sh_import_product_img)

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

    def perform_the_action(self, record):
        res = super(ImportProductImage, self).perform_the_action(record)
        if record.base_id.sh_technical_name == 'sh_import_product_img':
            self.import_product_image(record)
        return res

    def import_product_image(self, record):
        self = record
        if self and self.sh_file:
            # For CSV
            if self.import_type == 'csv':
                counter = 1
                skipped_line_no = {}
                try:
                    sh_file = str(base64.decodebytes(
                        self.sh_file).decode('utf-8'))
                    length_r = csv.reader(sh_file.splitlines())
                    length_reader = len(list(length_r))
                    myreader = csv.reader(sh_file.splitlines())
                    myreader = list(myreader)
                    count = 0
                    if self.import_limit == 0 or self.count_start_from+self.import_limit > length_reader:
                        till = length_reader
                    else:
                        till = self.count_start_from+self.import_limit
                    for row in range(self.count_start_from, till):
                        row = myreader[row]
                        try:
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
                                if self.product_by == 'name':
                                    field_nm = 'name'
                                elif self.product_by == 'int_ref':
                                    field_nm = 'default_code'
                                elif self.product_by == 'barcode':
                                    field_nm = 'barcode'

                                product_obj = False
                                if self.product_model == 'pro_var':
                                    product_obj = self.env["product.product"]
                                else:
                                    product_obj = self.env["product.template"]

                                search_product = product_obj.search(
                                    [(field_nm, '=', row[0])], limit=1)
                                if search_product:
                                    search_product.write(vals)
                                    counter = counter + 1
                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Product not found. "
                                    counter = counter + 1
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Product or URL/Path field is empty. "
                                counter = counter + 1
                                continue

                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid. " + ustr(e)
                            counter = counter + 1
                            continue
                        count += 1
                        self.current_count += 1
                        if count == self.import_limit:
                            self.count_start_from += self.import_limit
                    if self.current_count >= (length_reader-1):
                        if self.received_error:
                            self.state = 'partial_done'
                        else:
                            self.state = 'done'
                            self.count_start_from = 1
                            self.current_count = 0
                except Exception:
                    raise UserError(
                        _("Sorry, Your csv file does not match with our format"))
                if counter > 1:
                    completed_records = (counter - len(skipped_line_no)) - 1
                    if not skipped_line_no:
                        self.create_store_logs(
                            completed_records, skipped_line_no)
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

            # For Excel
            if self.import_type == 'excel':
                counter = 1
                skipped_line_no = {}
                try:
                    wb = xlrd.open_workbook(
                        file_contents=base64.decodebytes(self.sh_file))
                    sheet = wb.sheet_by_index(0)
                    count = 0
                    if self.import_limit == 0 or self.count_start_from+self.import_limit > sheet.nrows:
                        till = sheet.nrows
                    else:
                        till = self.count_start_from+self.import_limit
                    for row in range(self.count_start_from, till):
                        try:
                            if sheet.cell(row, 0).value not in (None, "") and sheet.cell(row, 1).value.strip() not in (None, ""):
                                vals = {}
                                image_path = sheet.cell(row, 1).value.strip()
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
                                if self.product_by == 'name':
                                    field_nm = 'name'
                                elif self.product_by == 'int_ref':
                                    field_nm = 'default_code'
                                elif self.product_by == 'barcode':
                                    field_nm = 'barcode'

                                product_obj = False
                                if self.product_model == 'pro_var':
                                    product_obj = self.env["product.product"]
                                else:
                                    product_obj = self.env["product.template"]

                                search_product = product_obj.search(
                                    [(field_nm, '=', sheet.cell(row, 0).value)], limit=1)
                                if search_product:
                                    search_product.write(vals)
                                    counter = counter + 1
                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Product not found. "
                                    counter = counter + 1
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Product or URL/Path field is empty. "
                                counter = counter + 1
                                continue

                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid. " + ustr(e)
                            counter = counter + 1
                            continue
                        count += 1
                        self.current_count += 1
                        if count == self.import_limit:
                            self.count_start_from += self.import_limit
                            break
                    if self.current_count >= (sheet.nrows-1):
                        if self.received_error:
                            self.state = 'partial_done'
                        else:
                            self.state = 'done'
                        self.count_start_from = 1
                        self.current_count = 0
                except Exception:
                    raise UserError(
                        _("Sorry, Your excel file does not match with our format"))

                if counter > 1:
                    completed_records = (counter - len(skipped_line_no)) - 1
                    if not skipped_line_no:
                        self.create_store_logs(
                            completed_records, skipped_line_no)
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