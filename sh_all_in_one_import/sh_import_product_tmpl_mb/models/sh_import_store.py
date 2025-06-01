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
import requests
import codecs
import logging
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)


class ImportStore(models.Model):
    _inherit = "sh.import.store"

    def check_sh_import_product_temp_mb(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_product_tmpl_mb':
            value = True
        return value

    sh_import_product_tmpl_mb_type = fields.Selection(
        related="base_id.sh_import_product_tmpl_mb_type", readonly=False, string="  Import File Type ", required=True)
    sh_import_product_tmpl_mb_method = fields.Selection(related="base_id.sh_import_product_tmpl_mb_method",
                                          readonly=False, string="Method", required=True)
    sh_import_product_tmpl_mb_product_update_by = fields.Selection(
        related="base_id.sh_import_product_tmpl_mb_product_update_by", readonly=False, string=" Product Update By", required=True)
    sh_import_product_tmpl_mb_update_existing = fields.Boolean(related="base_id.sh_import_product_tmpl_mb_update_existing",string="Remove Existing",readonly=False)
    sh_import_product_temp_mb_boolean = fields.Boolean(
        "Import Product Template MB Boolean", default=check_sh_import_product_temp_mb)
    sh_company_id_product_temp_mb = fields.Many2one(
        related="base_id.sh_company_id_product_temp_mb", readonly=False, string="Company", required=True)

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
        if record.base_id.sh_technical_name == 'sh_import_product_tmpl_mb':
            self.import_product_temp_mb(record)
        return res

    def validate_field_value(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        """ Validate field value, depending on field type and given value """
        self.ensure_one()

        try:
            checker = getattr(self, 'validate_field_' + field_ttype)
        except AttributeError:
            _logger.warning(
                field_ttype + ": This type of field has no validation method")
            return {}
        else:
            return checker(field_name, field_ttype, field_value, field_required, field_name_m2o)

    def validate_field_many2many(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            name_relational_model = self.env['product.template'].fields_get()[
                field_name]['relation']

            ids_list = []
            if field_value.strip() not in (None, ""):
                for x in field_value.split(','):
                    x = x.strip()
                    if x != '':
                        record = self.env[name_relational_model].sudo().search([
                            (field_name_m2o, '=', x)
                        ], limit=1)

                        if record:
                            ids_list.append(record.id)
                        else:
                            return {"error": " - " + x + " not found. "}
                            break

            return {field_name: [(6, 0, ids_list)]}

    def validate_field_many2one(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            name_relational_model = self.env['product.template'].fields_get()[
                field_name]['relation']
            record = self.env[name_relational_model].sudo().search([
                (field_name_m2o, '=', field_value)
            ], limit=1)
            return {field_name: record.id if record else False}

    def validate_field_text(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            return {field_name: field_value or False}

    def validate_field_integer(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            return {field_name: field_value or False}

    def validate_field_float(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            return {field_name: field_value or False}

    def validate_field_char(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            return {field_name: field_value or False}

    def validate_field_boolean(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        boolean_field_value = False
        if field_value.strip() == 'TRUE':
            boolean_field_value = True

        return {field_name: boolean_field_value}

    def validate_field_selection(self, field_name, field_ttype, field_value, field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}

        # get selection field key and value.
        selection_key_value_list = self.env['product.template'].sudo(
        )._fields[field_name].selection
        if selection_key_value_list and field_value not in (None, ""):
            for tuple_item in selection_key_value_list:
                if tuple_item[1] == field_value:
                    return {field_name: tuple_item[0] or False}

            return {"error": " - " + field_name + " given value " + str(field_value) + " does not match for selection. "}

        # finaly return false
        if field_value in (None, ""):
            return {field_name: False}

        return {field_name: field_value or False}

    def import_product_temp_mb(self,record):
        self = record
        product_tmpl_obj = self.env['product.template']
        ir_model_fields_obj = self.env['ir.model.fields']

        # perform import lead
        if self and self.sh_file:

            # For CSV
            if self.sh_import_product_tmpl_mb_type == 'csv' or self.sh_import_product_tmpl_mb_type == 'excel':
                counter = 1
                skipped_line_no = {}
                row_field_dic = {}
                row_field_error_dic = {}
                count=0
                try:
                    if self.sh_import_product_tmpl_mb_type == 'csv':
                        sh_file = str(base64.decodebytes(
                            self.sh_file).decode('utf-8'))
                        length_r = csv.reader(sh_file.splitlines())
                        length_reader = len(list(length_r))
                        myreader = csv.reader(sh_file.splitlines())
                        myreader = list(myreader)                       
                    elif self.sh_import_product_tmpl_mb_type == 'excel':
                        myreader=self.read_xls_book()                       
                        length_reader = len(myreader)

                    skip_header = True
                    till = length_reader
                    if self.import_limit == 0 or self.count_start_from+self.import_limit > length_reader:
                        till = length_reader
                    else:
                        till = self.count_start_from+self.import_limit   
                    created_product_tmpl = False
                    for row in range(self.count_start_from - 1, till):
                        try:
                            row = myreader[row] 
                            count += 1 
                            self.current_count += 1                                                       
                            if count == self.import_limit:
                                self.count_start_from += self.import_limit   
                            if skip_header:   
                                skip_header = False        
                                
                                for i in range(20, len(row)):
                                    name_field = row[i]
                                    name_m2o = False
                                    if '@' in row[i]:
                                        list_field_str = name_field.split('@')
                                        name_field = list_field_str[0]
                                        name_m2o = list_field_str[1]
                                    search_field = ir_model_fields_obj.sudo().search([
                                        ("model", "=", "product.template"),
                                        ("name", "=", name_field),
                                        ("store", "=", True),
                                    ], limit=1)

                                    if search_field:
                                        field_dic = {
                                            'name': name_field,
                                            'ttype': search_field.ttype,
                                            'required': search_field.required,
                                            'name_m2o': name_m2o
                                        }
                                        row_field_dic.update({i: field_dic})
                                    else:
                                        row_field_error_dic.update(
                                            {row[i]: " - field not found"})
                                continue

                            # ====================================================
                            # check if any error in dynamic field
                            # ====================================================
                            if row_field_error_dic:
                                self.create_store_logs(0, row_field_error_dic)
                                self.state = 'error'
                                break
                            if row[0].strip() not in (None, ""):
                                vals = {}
                                if row[1] not in ("",None) and row[1].strip() == 'FALSE':
                                    vals.update({
                                        'sale_ok':False
                                    })
                                elif row[1] not in ("",None) and row[1].strip() == 'TRUE':
                                    vals.update({
                                        'sale_ok':True
                                    })
                                if row[2] not in ("",None) and row[2].strip() == 'FALSE':
                                    vals.update({
                                        'purchase_ok':False
                                    })
                                elif row[2] not in ("",None) and row[2].strip() == 'TRUE':
                                    vals.update({
                                        'purchase_ok':True
                                    })
                                if row[3].strip() not in ("",False,None) and row[3].strip() == 'Service':
                                    vals.update({
                                        'type': 'service',
                                    })
                                elif row[3].strip() not in ("",False,None) and row[3].strip() == 'Storable Product' or row[3].strip() == 'Stockable Product':
                                    vals.update({
                                        'type': 'product',
                                    })
                                elif row[3].strip() not in ("",False,None) and row[3].strip() == 'Consumable':
                                    vals.update({
                                        'type': 'consu',
                                    })

                                categ_id = False
                                if row[4].strip() in (None, ""):
                                    search_category = self.env['product.category'].search(
                                        [('complete_name', '=', 'All')], limit=1)
                                    if search_category:
                                        categ_id = search_category.id
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Category - All not found. "
                                        counter = counter + 1
                                        continue
                                else:
                                    search_category = self.env['product.category'].search(
                                        [('complete_name', '=', row[4].strip())], limit=1)
                                    if search_category:
                                        categ_id = search_category.id
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Category not found. "
                                        counter = counter + 1
                                        continue

                                uom_id = False
                                if row[9].strip() in (None, ""):
                                    search_uom = self.env['uom.uom'].search(
                                        [('name', '=', 'Units')], limit=1)
                                    if search_uom:
                                        uom_id = search_uom.id
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Unit of Measure - Units not found. "
                                        counter = counter + 1
                                        continue
                                else:
                                    search_uom = self.env['uom.uom'].search(
                                        [('name', '=', row[9].strip())], limit=1)
                                    if search_uom:
                                        uom_id = search_uom.id
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Unit of Measure not found. "
                                        counter = counter + 1
                                        continue

                                uom_po_id = False
                                if row[10].strip() in (None, ""):
                                    search_uom_po = self.env['uom.uom'].search(
                                        [('name', '=', 'Units')], limit=1)
                                    if search_uom_po:
                                        uom_po_id = search_uom_po.id
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Purchase Unit of Measure - Units not found. "
                                        counter = counter + 1
                                        continue
                                else:
                                    search_uom_po = self.env['uom.uom'].search(
                                        [('name', '=', row[10].strip())], limit=1)
                                    if search_uom_po:
                                        uom_po_id = search_uom_po.id
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Purchase Unit of Measure not found. "
                                        counter = counter + 1
                                        continue

                                customer_taxes_ids_list = []
                                some_taxes_not_found = False
                                if row[13].strip() not in (None, ""):
                                    for x in row[13].split(','):
                                        x = x.strip()
                                        if x != '':
                                            search_customer_tax = self.env['account.tax'].search(
                                                [('name', '=', x)], limit=1)
                                            if search_customer_tax:
                                                customer_taxes_ids_list.append(
                                                    search_customer_tax.id)
                                            else:
                                                some_taxes_not_found = True
                                                skipped_line_no[str(
                                                    counter)] = " - Customer Taxes " + x + " not found. "
                                                break
                                if some_taxes_not_found:
                                    counter = counter + 1
                                    continue

                                vendor_taxes_ids_list = []

                                some_taxes_not_found = False
                                if row[14].strip() not in (None, ""):
                                    for x in row[14].split(','):
                                        x = x.strip()
                                        if x != '':
                                            search_vendor_tax = self.env['account.tax'].search(
                                                [('name', '=', x)], limit=1)
                                            if search_vendor_tax:
                                                vendor_taxes_ids_list.append(
                                                    search_vendor_tax.id)
                                            else:
                                                some_taxes_not_found = True
                                                skipped_line_no[str(
                                                    counter)] = " - Vendor Taxes " + x + " not found. "
                                                break

                                if some_taxes_not_found:
                                    counter = counter + 1
                                    continue

                                invoicing_policy = 'order'
                                if row[15].strip() == 'Delivered quantities':
                                    invoicing_policy = 'delivery'
                                if customer_taxes_ids_list:
                                    vals.update({
                                        'taxes_id': [(6, 0, customer_taxes_ids_list)],
                                    })
                                if vendor_taxes_ids_list:
                                    vals.update({
                                        'supplier_taxes_id': [(6, 0, vendor_taxes_ids_list)],
                                    })
                                if row[7] not in ("",False,None,0,0.0,'0','0.0'):
                                    vals.update({
                                        'list_price': row[7],
                                    })
                                if row[8] not in ("",False,None,0,0.0,'0','0.0'):
                                    vals.update({
                                        'standard_price': row[8],
                                    })
                                if row[11] not in ("",False,None,0,0.0,'0','0.0'):
                                    vals.update({
                                        'weight': row[11],
                                    })
                                if row[12] not in ("",False,None,0,0.0,'0','0.0'):
                                    vals.update({
                                        'volume': row[12],
                                    })
                                if row[16] not in ("",False,None,0,0.0,'0','0.0'):
                                    vals.update({
                                        'description_sale': row[16],
                                    })
                                vals = {
                                    'name': row[0].strip(),
                                    'categ_id': categ_id,
                                    'uom_id': uom_id,
                                    'uom_po_id': uom_po_id,
                                    'invoice_policy': invoicing_policy,
                                }

                                if row[6].strip() not in (None, ""):
                                    barcode = row[6].strip()
                                    vals.update({'barcode': barcode})

                                if row[5].strip() not in (None, ""):
                                    default_code = row[5].strip()
                                    vals.update({'default_code': default_code})

                                if row[18].strip() not in (None, ""):
                                    image_path = row[18].strip()
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
                                                        counter)] = " - Could not find the image or please make sure it is accessible to this user. "
                                                    counter = counter + 1
                                                    continue
                                        except Exception as e:
                                            skipped_line_no[str(
                                                counter)] = " - Could not find the image or please make sure it is accessible to this user " + ustr(e)
                                            counter = counter + 1
                                            continue

                                created_product_tmpl = False

                                # ===========================================================
                                # dynamic field logic start here
                                # ===========================================================

                                is_any_error_in_dynamic_field = False
                                for k_row_index, v_field_dic in row_field_dic.items():

                                    field_name = v_field_dic.get("name")
                                    field_ttype = v_field_dic.get("ttype")
                                    field_value = row[k_row_index]
                                    field_required = v_field_dic.get(
                                        "required")
                                    field_name_m2o = v_field_dic.get(
                                        "name_m2o")

                                    dic = self.validate_field_value(
                                        field_name, field_ttype, field_value, field_required, field_name_m2o)
                                    if dic.get("error", False):
                                        skipped_line_no[str(counter)] = dic.get(
                                            "error")
                                        is_any_error_in_dynamic_field = True
                                        break
                                    else:
                                        vals.update(dic)

                                if is_any_error_in_dynamic_field:
                                    counter = counter + 1
                                    continue
                                # ===========================================================
                                # dynamic field logic end here
                                # ===========================================================

                                if self.sh_import_product_tmpl_mb_method == 'create':
                                    barcode_list = []
                                    if row[19].strip() not in (None, ""):
                                        exist_barcode=[]
                                        for x in row[19].split(','):
                                            x = x.strip()
                                            search_barcode = self.env['product.product'].search(
                                                ['|', ('barcode_line_ids.name', '=', x), ('barcode', '=', x)], limit=1)
                                            if not search_barcode:
                                                if x != '':
                                                    barcode_vals = {
                                                        'name': x
                                                    }
                                                    barcode_list.append(
                                                        (0, 0, barcode_vals))
                                            else:
                                                exist_barcode.append(x)
                                        if exist_barcode:
                                            skipped_line_no[str(
                                                counter)] = " - Barcode already exist."
                                            counter = counter + 1
                                            continue
                                    if row[6].strip() in (None, ""):
                                        created_product_tmpl = product_tmpl_obj.create(
                                            vals)
                                        created_product_tmpl.barcode_line_ids = barcode_list
                                        counter = counter + 1
                                    else:
                                        search_product_tmpl = product_tmpl_obj.search(
                                            [('barcode', '=', row[6].strip())], limit=1)
                                        if search_product_tmpl:
                                            skipped_line_no[str(
                                                counter)] = " - Barcode already exist. "
                                            counter = counter + 1
                                            continue
                                        else:
                                            created_product_tmpl = product_tmpl_obj.create(
                                                vals)
                                            created_product_tmpl.barcode_line_ids = barcode_list
                                            counter = counter + 1
                                elif self.sh_import_product_tmpl_mb_method == 'write' and self.sh_import_product_tmpl_mb_product_update_by == 'barcode':
                                    if row[6].strip() in (None, ""):
                                        created_product_tmpl = product_tmpl_obj.create(
                                            vals)
                                        counter = counter + 1
                                    else:
                                        search_product_tmpl = product_tmpl_obj.search(
                                            [('barcode', '=', row[6].strip())], limit=1)
                                        if search_product_tmpl:
                                            created_product_tmpl = search_product_tmpl
                                            search_product_tmpl.write(vals)
                                            counter = counter + 1
                                        else:
                                            created_product_tmpl = product_tmpl_obj.create(
                                                vals)
                                            counter = counter + 1
                                elif self.sh_import_product_tmpl_mb_method == 'write' and self.sh_import_product_tmpl_mb_product_update_by == 'int_ref':
                                    search_product_tmpl = product_tmpl_obj.search(
                                        [('default_code', '=', row[5].strip())], limit=1)
                                    if search_product_tmpl:
                                        if row[6].strip() in (None, ""):
                                            created_product_tmpl = search_product_tmpl
                                            search_product_tmpl.write(vals)
                                            counter = counter + 1
                                        else:
                                            search_product_tmpl_bar = product_tmpl_obj.search(
                                                [('barcode', '=', row[6].strip())], limit=1)
                                            if search_product_tmpl_bar:
                                                skipped_line_no[str(
                                                    counter)] = " - Barcode already exist. "
                                                counter = counter + 1
                                                continue
                                            else:
                                                created_product_tmpl = search_product_tmpl
                                                search_product_tmpl.write(vals)
                                                counter = counter + 1
                                    else:
                                        if row[6].strip() in (None, ""):
                                            created_product_tmpl = product_tmpl_obj.create(
                                                vals)
                                            counter = counter + 1
                                        else:
                                            search_product_tmpl_bar = product_tmpl_obj.search(
                                                [('barcode', '=', row[6].strip())], limit=1)
                                            if search_product_tmpl_bar:
                                                skipped_line_no[str(
                                                    counter)] = " - Barcode already exist. "
                                                counter = counter + 1
                                                continue
                                            else:
                                                created_product_tmpl = product_tmpl_obj.create(
                                                    vals)
                                                counter = counter + 1

                                if created_product_tmpl and self.sh_import_product_tmpl_mb_method == 'write':
                                    barcode_list = []
                                    if not self.sh_import_product_tmpl_mb_update_existing:
                                        if row[19].strip() not in (None, ""):
                                            for x in row[19].split(','):
                                                x = x.strip()
                                                if x != '':
                                                    search_barcode = self.env['product.product'].search(
                                                        ['|', ('barcode_line_ids.name', '=', x), ('barcode', '=', x)], limit=1)
                                                    if not search_barcode:
                                                        self.env['product.template.barcode'].sudo().create({
                                                            'name': x,
                                                            'product_id': created_product_tmpl.product_variant_id.id,
                                                        })
                                    else:
                                        created_product_tmpl.barcode_line_ids = False
                                        if row[19].strip() not in (None, ""):
                                            for x in row[19].split(','):
                                                x = x.strip()
                                                search_barcode = self.env['product.product'].search(
                                                    ['|', ('barcode_line_ids.name', '=', x), ('barcode', '=', x)], limit=1)
                                                if not search_barcode:
                                                    if x != '':
                                                        barcode_vals = {
                                                            'name': x
                                                        }
                                                        barcode_list.append(
                                                            (0, 0, barcode_vals))
                                    created_product_tmpl.barcode_line_ids = barcode_list
                                if created_product_tmpl and created_product_tmpl.product_variant_id and created_product_tmpl.type == 'product' and row[17] != '':
                                    stock_vals = {'product_tmpl_id': created_product_tmpl.id,
                                                  'new_quantity': row[17],
                                                  'product_id': created_product_tmpl.product_variant_id.id
                                                  }
                                    created_qty_on_hand = self.env['stock.change.product.qty'].create(
                                        stock_vals)
                                    if created_qty_on_hand:
                                        created_qty_on_hand.change_product_qty()

                            else:
                                skipped_line_no[str(
                                    counter)] = " - Name is empty. "
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

