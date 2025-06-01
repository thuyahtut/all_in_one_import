# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from email.policy import default
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
import logging
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)


class ImportStore(models.Model):
    _inherit = "sh.import.store"

    def check_sh_import_product_var_mb(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_product_var_mb':
            value = True
        return value

    sh_import_product_var_mb_type = fields.Selection(
        related="base_id.sh_import_product_var_mb_type", readonly=False, string="  Import File Type ", required=True)
    sh_import_product_var_mb_method = fields.Selection(related='base_id.sh_import_product_var_mb_method',string="Method",required=True, readonly=False)
    sh_import_product_var_mb_product_update_by = fields.Selection(
        related="base_id.sh_import_product_var_mb_product_update_by", readonly=False, string=" Product Variant Update By", required=True)
    sh_import_product_var_mb_update_existing = fields.Boolean(related='base_id.sh_import_product_var_mb_update_existing',readonly=False,string="Remove Existing")
    sh_import_product_var_mb_is_create_m2m_record = fields.Boolean(
        related="base_id.sh_import_product_var_mb_is_create_m2m_record", readonly=False,string="Create a New Record for Dynamic M2M Field (if not exist)?")

    sh_import_product_var_mb_is_create_categ_id_record = fields.Boolean(
        related="base_id.sh_import_product_var_mb_is_create_categ_id_record", readonly=False,string="Create a New Record for Product Category Field (if not exist)?"
    )
    sh_import_product_var_mb_boolean = fields.Boolean(
        "Import Variant Boolean", default=check_sh_import_product_var_mb)
    sh_company_id_product_var_mb = fields.Many2one(
        related="base_id.sh_company_id_product_var_mb", readonly=False, string="Company", required=True)
    running_tmpl_var_mb = fields.Char(string='Running Template Var MB')
    total_done_tmpl_var_mb = fields.Integer("Total Done Template Var MB")

    def create_product_var_mb_logs(self, counter, skipped_line_no):
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
        if record.base_id.sh_technical_name == 'sh_import_product_var_mb':
            self.import_product_var_mb(record)
        return res

    def create_internal_category(self, categ_complete_name):
        categs_ids_list = []
        previous_categ = False
        for x in categ_complete_name.split('/'):
            x = x.strip()
            if x != '':
                search_categ = self.env['product.category'].sudo().search(
                    [('name', '=', x)], limit=1)
                if search_categ:
                    categs_ids_list.append(search_categ.id)
                    if previous_categ:
                        search_categ.update({'parent_id': previous_categ})
                    previous_categ = search_categ.id
                else:
                    # create new one
                    if previous_categ:
                        categ_id = self.env['product.category'].sudo().create({
                            'name':
                            x,
                            'parent_id':
                            previous_categ
                        })
                    else:
                        categ_id = self.env['product.category'].sudo().create(
                            {'name': x})
                    categs_ids_list.append(categ_id.id)

                    previous_categ = categ_id.id
    # ====================================================================================
    # Validation methods for custom field
    # ====================================================================================

    def validate_field_value(self, field_name, field_ttype, field_value,
                             field_required, field_name_m2o):
        """ Validate field value, depending on field type and given value """
        self.ensure_one()

        try:
            checker = getattr(self, 'validate_field_' + field_ttype)
        except AttributeError:
            _logger.warning(field_ttype +
                            ": This type of field has no validation method")
            return {}
        else:
            return checker(field_name, field_ttype, field_value,
                           field_required, field_name_m2o)

    def validate_field_many2many(self, field_name, field_ttype, field_value,
                                 field_required, field_name_m2o):
        self.ensure_one()

        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            name_relational_model = self.env['product.product'].fields_get(
            )[field_name]['relation']

            ids_list = []
            if field_value.strip() not in (None, ""):
                for x in field_value.split(','):
                    x = x.strip()
                    if x != '':
                        record = self.env[name_relational_model].sudo().search(
                            [(field_name_m2o, '=', x)], limit=1)

                        # ---------------------------------------------------------
                        # if m2m record not found then create a new record for it.
                        # if tick in wizard.

                        if self.sh_import_product_var_mb_is_create_m2m_record and not record:
                            try:
                                record = self.env[name_relational_model].sudo(
                                ).create({field_name_m2o: x})
                            except Exception as e:
                                msg = " - Value is not valid. " + ustr(e)
                                return {"error": " - " + x + msg}
                                break
                        # ---------------------------------------------------------
                        # if m2m record not found then create a new record for it.

                        if record:
                            ids_list.append(record.id)
                        else:
                            return {"error": " - " + x + " not found. "}
                            break

            return {field_name: [(6, 0, ids_list)]}

    def validate_field_many2one(self, field_name, field_ttype, field_value,
                                field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            name_relational_model = self.env['product.product'].fields_get(
            )[field_name]['relation']
            record = self.env[name_relational_model].sudo().search(
                [(field_name_m2o, '=', field_value)], limit=1)
            return {field_name: record.id if record else False}

    def validate_field_text(self, field_name, field_ttype, field_value,
                            field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            return {field_name: field_value or False}

    def validate_field_integer(self, field_name, field_ttype, field_value,
                               field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            return {field_name: field_value or False}

    def validate_field_float(self, field_name, field_ttype, field_value,
                             field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            return {field_name: field_value or False}

    def validate_field_char(self, field_name, field_ttype, field_value,
                            field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}
        else:
            return {field_name: field_value or False}

    def validate_field_boolean(self, field_name, field_ttype, field_value,
                               field_required, field_name_m2o):
        self.ensure_one()
        boolean_field_value = False
        if field_value.strip() == 'TRUE':
            boolean_field_value = True

        return {field_name: boolean_field_value}

    def validate_field_selection(self, field_name, field_ttype, field_value,
                                 field_required, field_name_m2o):
        self.ensure_one()
        if field_required and field_value in (None, ""):
            return {"error": " - " + field_name + " is required. "}

        # get selection field key and value.
        selection_key_value_list = self.env['product.product'].sudo(
        )._fields[field_name].selection
        if not isinstance(selection_key_value_list, list):
            selection_key_value_list = self.env['product.template'].sudo(
            )._fields[field_name].selection
        if selection_key_value_list and field_value not in (None, ""):
            for tuple_item in selection_key_value_list:
                if tuple_item[1] == field_value:
                    return {field_name: tuple_item[0] or False}

            return {
                "error":
                " - " + field_name + " given value " + str(field_value) +
                " does not match for selection. "
            }

        # finaly return false
        if field_value in (None, ""):
            return {field_name: False}

        return {field_name: field_value or False}

    def import_product_var_mb(self,record):
        self = record
        product_tmpl_obj = self.env['product.template']
        ir_model_fields_obj = self.env['ir.model.fields']

        # perform import lead
        if self and self.sh_file:

            # For CSV
            if self.import_type == 'csv' or self.import_type == 'excel':
                counter = 1
                skipped_line_no = {}
                row_field_dic = {}
                row_field_error_dic = {}
                count=0
                imported_lines = 0
                try:
                    if self.import_type == 'csv':
                        sh_file = str(base64.decodebytes(
                            self.sh_file).decode('utf-8'))
                        length_r = csv.reader(sh_file.splitlines())
                        length_reader = len(list(length_r))
                        myreader = csv.reader(sh_file.splitlines())
                        myreader = list(myreader)                       
                    elif self.import_type == 'excel':
                        myreader=self.read_xls_book()                       
                        length_reader = len(myreader)

                    skip_header = True
                    # running_tmpl = None
                    created_product_tmpl = False
                    has_variant = False
                    running_tmpl_domain = []

                    list_to_keep_attr = []
                    list_to_keep_attr_value = []
                    till = length_reader
                    if self.import_limit == 0 or self.count_start_from+self.import_limit > length_reader:
                        till = length_reader
                    else:
                        till = self.count_start_from+self.import_limit
                    self.total_done_tmpl_var_mb = till
                    for row in range(self.count_start_from - 1, till):
                        try:
                            created_product_tmpl = product_tmpl_obj.sudo().search([('name','=',self.running_tmpl_var_mb)],limit=1)
                            row = myreader[row] 
                            count += 1 
                            self.current_count += 1                                                       
                            if count == self.import_limit:
                                self.count_start_from += self.import_limit   
                            if skip_header:   
                                skip_header = False        
                                
                                for i in range(24, len(row)):
                                    name_field = row[i]
                                    name_m2o = False
                                    if '@' in row[i]:
                                        list_field_str = name_field.split('@')
                                        name_field = list_field_str[0]
                                        name_m2o = list_field_str[1]
                                    search_field = ir_model_fields_obj.sudo(
                                    ).search(
                                        [
                                            ("model", "=", "product.product"),
                                            ("name", "=", name_field),
                                            # ("store", "=", True),
                                        ],
                                        limit=1)
                                    if not search_field:
                                        search_field = ir_model_fields_obj.sudo(
                                        ).search(
                                            [
                                                ("model", "=",
                                                    "product.template"),
                                                ("name", "=", name_field),
                                                # ("store", "=", True),
                                            ],
                                            limit=1)

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
                                self.create_product_var_mb_logs(0, row_field_error_dic)
                                self.state = 'error'
                                break
                                # res = self.show_success_msg(
                                #     0, row_field_error_dic)
                                # return res

                            # ====================================================
                            # check if any error in dynamic field
                            # ====================================================
                            if row[0] not in (None,
                                              "") and row[1] not in (None, ""):
                                var_vals = {}

                                # Product Template Start
                                if row[0] != self.running_tmpl_var_mb:
                                    self.running_tmpl_var_mb = row[0]

                                    # =====================================
                                    # Search or Update product by
                                    # =====================================

                                    if self.product_update_by == 'name':
                                        running_tmpl_domain = [
                                            ('name', '=', row[1]),
                                        ]

                                    elif self.product_update_by == 'barcode':
                                        running_tmpl_domain = [
                                            ('product_variant_ids.barcode',
                                             '=', row[17]),
                                        ]

                                    elif self.product_update_by == 'int_ref':
                                        running_tmpl_domain = [
                                            ('product_variant_ids.default_code',
                                             '=', row[16]),
                                        ]

                                    # =====================================
                                    # Search or Update product by
                                    # =====================================

                                    # TODO: NEED TO CLEAN LAST PRODUCT ALSO.
                                    if created_product_tmpl and self.method == 'write':

                                        # Remove Unnecessary Attribute Line.
                                        # ===============================================
                                        attrs = created_product_tmpl.attribute_line_ids.mapped(
                                            'attribute_id').filtered(
                                                lambda r: r.id not in
                                                list_to_keep_attr)
                                        for attr in attrs:
                                            line = created_product_tmpl.attribute_line_ids.search(
                                                [
                                                    ('attribute_id', '=',
                                                     attr.id),
                                                    ('product_tmpl_id', '=',
                                                     created_product_tmpl.id),
                                                ],
                                                limit=1)
                                            if line:
                                                line.unlink()

                                        # Remove Unnecessary Attribute Line.
                                        # ===============================================

                                        # Remove Unnecessary Attribute Value From Line.
                                        # ===============================================
                                        attr_values = created_product_tmpl.attribute_line_ids.mapped(
                                            'value_ids').filtered(
                                                lambda r: r.id not in
                                                list_to_keep_attr_value)
                                        for attr_value in attr_values:
                                            line = created_product_tmpl.attribute_line_ids.search(
                                                [
                                                    ('value_ids', 'in',
                                                     attr_value.ids),
                                                    ('product_tmpl_id', '=',
                                                     created_product_tmpl.id),
                                                ],
                                                limit=1)
                                            if line:
                                                line.write({
                                                    'value_ids':
                                                    [(3, attr_value.id, 0)],
                                                })

                                        # Remove Unnecessary Attribute Value From Line.
                                        # ===============================================

                                        created_product_tmpl._create_variant_ids(
                                        )
                                        list_to_keep_attr = []
                                        list_to_keep_attr_value = []

                                    tmpl_vals = {}
                                    tmpl_vals.update({'name': row[1]})
                                    if row[2].strip() not in ("",None) and row[2].strip() == 'FALSE':
                                        tmpl_vals.update({'sale_ok': False})
                                    elif row[2].strip() not in ("",None) and row[2].strip() == 'TRUE':
                                        tmpl_vals.update({'sale_ok': True})
                                    if row[3].strip() not in ("",None) and row[3].strip() == 'FALSE':
                                        tmpl_vals.update({'purchase_ok': False})
                                    elif row[3].strip() not in ("",None) and row[3].strip() == 'TRUE':
                                        tmpl_vals.update({'purchase_ok': True})
                                    if row[4] not in ("",None,False) and row[4].strip() == 'Service':
                                        tmpl_vals.update({'type': 'service'})
                                    elif row[4] not in ("",None,False) and row[4].strip() == 'Storable Product' or row[4].strip() == 'Stockable Product':
                                        tmpl_vals.update({'type': 'product'})
                                    elif row[4] not in ("",None,False) and row[4].strip() == 'Consumable':
                                        tmpl_vals.update({'type': 'consu'})
                                    if row[5].strip() in (None, ""):
                                        search_category = self.env[
                                            'product.category'].search([
                                                ('complete_name', '=', 'All')
                                            ],
                                            limit=1)
                                        if search_category:
                                            tmpl_vals.update({
                                                'categ_id':
                                                search_category.id
                                            })
                                        else:
                                            skipped_line_no[str(
                                                counter
                                            )] = " - Category - All  not found. "
                                            counter = counter + 1
                                            continue
                                    else:
                                        search_category = self.env[
                                            'product.category'].search(
                                                [('complete_name', '=',
                                                  row[5].strip())],
                                                limit=1)

                                        # -----------------------------------------
                                        # if category not found then create new
                                        # client specific.
                                        if not search_category:
                                            if self.sh_import_product_var_mb_is_create_categ_id_record:
                                                self.create_internal_category(
                                                    row[5].strip())

                                                search_category = self.env[
                                                    'product.category'].search(
                                                        [('complete_name', '=',
                                                          row[5].strip())],
                                                        limit=1)

                                        # -----------------------------------------
                                        # if category not found then create new

                                        if search_category:
                                            tmpl_vals.update({
                                                'categ_id':
                                                search_category.id
                                            })
                                        else:
                                            skipped_line_no[str(
                                                counter
                                            )] = " - Category - %s not found. " % (
                                                row[5].strip())
                                            counter = counter + 1
                                            continue
                                    if row[6].strip() in (None, ""):
                                        search_uom = self.env[
                                            'uom.uom'].search(
                                                [('name', '=', 'Units')],
                                                limit=1)
                                        if search_uom:
                                            tmpl_vals.update(
                                                {'uom_id': search_uom.id})
                                        else:
                                            skipped_line_no[str(
                                                counter
                                            )] = " - Unit of Measure - Units not found. "
                                            counter = counter + 1
                                            continue
                                    else:
                                        search_uom = self.env[
                                            'uom.uom'].search([
                                                ('name', '=', row[6].strip())
                                            ],
                                            limit=1)
                                        if search_uom:
                                            tmpl_vals.update(
                                                {'uom_id': search_uom.id})
                                        else:
                                            skipped_line_no[str(
                                                counter
                                            )] = " - Unit of Measure not found. "
                                            counter = counter + 1
                                            continue

                                    if row[7].strip() in (None, ""):
                                        search_uom_po = self.env[
                                            'uom.uom'].search(
                                                [('name', '=', 'Units')],
                                                limit=1)
                                        if search_uom_po:
                                            tmpl_vals.update({
                                                'uom_po_id':
                                                search_uom_po.id
                                            })
                                        else:
                                            skipped_line_no[str(
                                                counter
                                            )] = " - Purchase Unit of Measure - Units not found. "
                                            counter = counter + 1
                                            continue
                                    else:
                                        search_uom_po = self.env[
                                            'uom.uom'].search([
                                                ('name', '=', row[7].strip())
                                            ],
                                            limit=1)
                                        if search_uom_po:
                                            tmpl_vals.update({
                                                'uom_po_id':
                                                search_uom_po.id
                                            })
                                        else:
                                            skipped_line_no[str(
                                                counter
                                            )] = " - Purchase Unit of Measure not found. "
                                            counter = counter + 1
                                            continue

                                    customer_taxes_ids_list = []
                                    some_taxes_not_found = False
                                    if row[8].strip() not in (None, ""):
                                        for x in row[8].split(','):
                                            x = x.strip()
                                            if x != '':
                                                search_customer_tax = self.env[
                                                    'account.tax'].search(
                                                        [('name', '=', x)],
                                                        limit=1)
                                                if search_customer_tax:
                                                    customer_taxes_ids_list.append(
                                                        search_customer_tax.id)
                                                else:
                                                    some_taxes_not_found = True
                                                    skipped_line_no[str(
                                                        counter
                                                    )] = " - Customer Taxes " + x + " not found. "
                                                    break

                                    if some_taxes_not_found:
                                        counter = counter + 1
                                        continue
                                    else:
                                        if customer_taxes_ids_list:
                                            tmpl_vals.update({
                                                'taxes_id':
                                                [(6, 0, customer_taxes_ids_list)]
                                            })

                                    vendor_taxes_ids_list = []
                                    some_taxes_not_found = False
                                    if row[9].strip() not in (None, ""):
                                        for x in row[9].split(','):
                                            x = x.strip()
                                            if x != '':
                                                search_vendor_tax = self.env[
                                                    'account.tax'].search(
                                                        [('name', '=', x)],
                                                        limit=1)
                                                if search_vendor_tax:
                                                    vendor_taxes_ids_list.append(
                                                        search_vendor_tax.id)
                                                else:
                                                    some_taxes_not_found = True
                                                    skipped_line_no[str(
                                                        counter
                                                    )] = " - Vendor Taxes " + x + " not found. "
                                                    break

                                    if some_taxes_not_found:
                                        counter = counter + 1
                                        continue
                                    else:
                                        if vendor_taxes_ids_list:
                                            tmpl_vals.update({
                                                'supplier_taxes_id':
                                                [(6, 0, vendor_taxes_ids_list)]
                                            })
                                    if row[10] not in ("",False,None):
                                        tmpl_vals.update(
                                            {'description_sale': row[10]})

                                    tmpl_vals.update(
                                        {'invoice_policy': 'order'})
                                    if row[11].strip(
                                    ) == 'Delivered quantities':
                                        tmpl_vals.update(
                                            {'invoice_policy': 'delivery'})

                                    if row[12] not in (None, "",False,0,0.0,'0','0.0'):
                                        tmpl_vals.update(
                                            {'list_price': float(row[12])})

                                    if row[13] not in (None, "",False,0,0.0,'0','0.0'):
                                        tmpl_vals.update(
                                            {'standard_price': float(row[13])})

                                    if row[14].strip() in (
                                            None,
                                            "") or row[15].strip() in (None,
                                                                       ""):

                                        has_variant = False
                                        if row[16] not in (None, ""):
                                            tmpl_vals.update(
                                                {'default_code': row[16]})

                                        if row[17] not in (None, ""):
                                            tmpl_vals.update(
                                                {'barcode': row[17]})

                                        if row[18] not in (None, "",False,0,0.0,'0','0.0'):
                                            tmpl_vals.update(
                                                {'weight': float(row[18])})

                                        if row[19] not in (None, "",False,0,0.0,'0','0.0'):
                                            tmpl_vals.update(
                                                {'volume': float(row[19])})

                                        if row[21].strip() not in (None, ""):
                                            image_path = row[21].strip()
                                            if "http://" in image_path or "https://" in image_path:
                                                try:
                                                    r = requests.get(
                                                        image_path)
                                                    if r and r.content:
                                                        image_base64 = base64.decodebytes(
                                                            r.content)
                                                        tmpl_vals.update({
                                                            'image_1920':
                                                            image_base64
                                                        })
                                                    else:
                                                        skipped_line_no[str(
                                                            counter
                                                        )] = " - URL not correct or check your image size. "
                                                        counter = counter + 1
                                                        continue
                                                except Exception as e:
                                                    skipped_line_no[str(
                                                        counter
                                                    )] = " - URL not correct or check your image size " + ustr(
                                                        e)
                                                    counter = counter + 1
                                                    continue

                                            else:
                                                try:
                                                    with open(
                                                            image_path,
                                                            'rb') as image:
                                                        image.seek(0)
                                                        binary_data = image.read(
                                                        )
                                                        image_base64 = codecs.encode(
                                                            binary_data,
                                                            'base64')
                                                        if image_base64:
                                                            tmpl_vals.update({
                                                                'image_1920':
                                                                image_base64
                                                            })
                                                        else:
                                                            skipped_line_no[str(
                                                                counter
                                                            )] = " - Could not find the image or please make sure it is accessible to this app. "
                                                            counter = counter + 1
                                                            continue
                                                except Exception as e:
                                                    skipped_line_no[str(
                                                        counter
                                                    )] = " - Could not find the image or please make sure it is accessible to this app. " + ustr(
                                                        e)
                                                    counter = counter + 1
                                                    continue

                                        # ============================
                                        # put multi barcode here

                                    else:
                                        has_variant = True

                                    # ===================================================================
                                    # Step 1: Search Product Template Here if exist than use it.
                                    # Search by name for now.
                                    if self.method == 'create':

                                        created_product_tmpl = product_tmpl_obj.create(
                                            tmpl_vals)

                                    elif self.method == 'write':
                                        # =====================================
                                        # Search or Update product by
                                        # =====================================

                                        search_product = product_tmpl_obj.search(
                                            running_tmpl_domain, limit=1)

                                        # =====================================
                                        # Search or Update product by
                                        # =====================================

                                        if search_product:
                                            # Write product Template Field.
                                            search_product.write(tmpl_vals)
                                            created_product_tmpl = search_product
                                        else:
                                            created_product_tmpl = product_tmpl_obj.create(
                                                tmpl_vals)

                                    # =================================================================


#                                     if created_product_tmpl and self.method == 'write':
#                                         created_product_tmpl.attribute_line_ids = False

                                    if has_variant == False and row[
                                            20] not in (None, ""):
                                        if created_product_tmpl and created_product_tmpl.product_variant_id and created_product_tmpl.type == 'product':
                                            stock_vals = {
                                                'product_tmpl_id':
                                                created_product_tmpl.id,
                                                'new_quantity':
                                                float(row[20]),
                                                'product_id':
                                                created_product_tmpl.
                                                product_variant_id.id
                                            }
                                            created_qty_on_hand = self.env[
                                                'stock.change.product.qty'].create(
                                                    stock_vals)
                                            if created_qty_on_hand:
                                                created_qty_on_hand.change_product_qty(
                                                )

                                    # code for if product variant has not attribute
                                    if has_variant == False and created_product_tmpl:

                                        barcode_list = []
                                        if row[22].strip() not in (None, ""):
                                            for x in row[22].split(','):
                                                x = x.strip()
                                                if x != '':
                                                    search_barcode = self.env[
                                                        'product.product'].search(
                                                            [
                                                                '|',
                                                                ('barcode_line_ids.name',
                                                                 '=', x),
                                                                ('barcode',
                                                                 '=', x)
                                                            ],
                                                            limit=1)
                                                    if not search_barcode:
                                                        barcode_vals = {
                                                            'name': x
                                                        }
                                                        barcode_list.append(
                                                            (0, 0,
                                                             barcode_vals))

                                        created_product_tmpl.barcode_line_ids = barcode_list

                                # Variant Values
                                if created_product_tmpl and has_variant:

                                    # Product Variants created part here

                                    pro_attr_line_obj = self.env[
                                        'product.template.attribute.line']
                                    pro_attr_value_obj = self.env[
                                        'product.attribute.value']
                                    pro_attr_obj = self.env[
                                        'product.attribute']
                                    if row[14].strip() not in (
                                            None, ""
                                    ) and row[15].strip() not in (None, ""):
                                        attr_ids_list = []
                                        for attr in row[14].split(','):
                                            attr = attr.strip()
                                            if attr != '':
                                                search_attr_name = False
                                                search_attr_name = pro_attr_obj.search(
                                                    [('name', '=', attr)],
                                                    limit=1)
                                                if not search_attr_name:
                                                    search_attr_name = pro_attr_obj.create(
                                                        {'name': attr})
                                                attr_ids_list.append(
                                                    search_attr_name.id)

                                        attr_value_list = []
                                        attr_value_price_dic = {}
                                        for attr_value in row[15].split('#'):
                                            attr_value = attr_value.strip()
                                            splited_attr_value_price_list = []

                                            # Product Attribute Price Start Here
                                            # attribute_value@attribute_price
                                            if '@' in attr_value:
                                                splited_attr_value_price_list = attr_value.split(
                                                    '@')
                                                if ',' in splited_attr_value_price_list[1]:
                                                    new_value = splited_attr_value_price_list[1].replace(
                                                        ",", ".")
                                                    attr_value_price_dic.update({
                                                        splited_attr_value_price_list[0]:
                                                        float(new_value)
                                                    })
                                                else:
                                                    attr_value_price_dic.update({
                                                        splited_attr_value_price_list[0]:
                                                        float(
                                                            splited_attr_value_price_list[1])
                                                    })
                                            else:
                                                splited_attr_value_price_list = [
                                                    attr_value
                                                ]
                                                # Product Attribute Price Ends Here

                                            if splited_attr_value_price_list[
                                                    0] != '':
                                                attr_value_list.append(
                                                    splited_attr_value_price_list[
                                                        0])

                                        attr_value_ids_list = []
                                        if len(attr_ids_list) == len(
                                                attr_value_list):
                                            i = 0
                                            while i < len(attr_ids_list):
                                                search_attr_value = False
                                                search_attr_value = pro_attr_value_obj.search(
                                                    [('name', '=',
                                                      attr_value_list[i]),
                                                     ('attribute_id', '=',
                                                      attr_ids_list[i])],
                                                    limit=1)

                                                if not search_attr_value:
                                                    search_attr_value = pro_attr_value_obj.create(
                                                        {
                                                            'name':
                                                            attr_value_list[i],
                                                            'attribute_id':
                                                            attr_ids_list[i]
                                                        })

                                                attr_value_ids_list.append(
                                                    search_attr_value.id)
                                                i += 1
                                        else:
                                            skipped_line_no[str(
                                                counter
                                            )] = " - Number of attributes and it's value not equal. "
                                            counter = counter + 1
                                            continue

                                        # To Keep Attribute Value List
                                        # =====================================
                                        if attr_value_ids_list:
                                            for item in attr_value_ids_list:
                                                if item not in list_to_keep_attr_value:
                                                    list_to_keep_attr_value.append(
                                                        item)

                                        # To Keep Attribute Value List
                                        # =====================================

                                        # To Keep Attribute  List
                                        # =====================================
                                        if attr_ids_list:
                                            for item in attr_ids_list:
                                                if item not in list_to_keep_attr:
                                                    list_to_keep_attr.append(
                                                        item)

                                        # To Keep Attribute  List
                                        # =====================================

                                        if self.method == 'create':
                                            if attr_value_ids_list and attr_ids_list:
                                                i = 0
                                                while i < len(attr_ids_list):
                                                    search_attr_line = pro_attr_line_obj.search(
                                                        [
                                                            ('attribute_id',
                                                             '=',
                                                             attr_ids_list[i]),
                                                            ('product_tmpl_id',
                                                             '=',
                                                             created_product_tmpl
                                                             .id),
                                                        ],
                                                        limit=1)
                                                    if search_attr_line:
                                                        past_values_list = []
                                                        past_values_list = search_attr_line.value_ids.ids
                                                        past_values_list.append(
                                                            attr_value_ids_list[
                                                                i])
                                                        search_attr_line.write({
                                                            'value_ids':
                                                            [(6, 0,
                                                              past_values_list)
                                                             ]
                                                        })
                                                    else:
                                                        pro_attr_line_obj.create({
                                                            'attribute_id':
                                                            attr_ids_list[i],
                                                            'value_ids':
                                                            [(6, 0, [
                                                                attr_value_ids_list[
                                                                    i]
                                                            ])],
                                                            'product_tmpl_id':
                                                            created_product_tmpl
                                                            .id,
                                                        })
                                                    i += 1

                                            created_product_tmpl._create_variant_ids(
                                            )
                                            if created_product_tmpl.product_variant_ids:

                                                product_var_obj = self.env[
                                                    'product.product']
                                                domain = []
                                                domain.append(
                                                    ('product_tmpl_id', '=',
                                                     created_product_tmpl.id))

                                                for attr_value_id in attr_value_ids_list:
                                                    domain.append((
                                                        'product_template_attribute_value_ids.product_attribute_value_id.id',
                                                        '=', attr_value_id))

                                                product_varient = product_var_obj.search(
                                                    domain, limit=1)
                                                if not product_varient:
                                                    skipped_line_no[str(
                                                        counter
                                                    )] = " - Product Variants not found."
                                                    counter = counter + 1
                                                    continue

                                                # update price extra start here
                                                if attr_value_price_dic:
                                                    product_tmpl_attribute_value_obj = self.env[
                                                        "product.template.attribute.value"]
                                                    extra_price = 0
                                                    for product_varient_attribute_value_id in product_varient.product_template_attribute_value_ids:
                                                        if attr_value_price_dic.get(
                                                                product_varient_attribute_value_id
                                                                .name, False):
                                                            extra_price = 0
                                                            if attr_value_price_dic.get(
                                                                    product_varient_attribute_value_id
                                                                    .name
                                                            ) not in [
                                                                    0, 0.0, '',
                                                                    "", None
                                                            ]:
                                                                extra_price = float(
                                                                    attr_value_price_dic
                                                                    .get(
                                                                        product_varient_attribute_value_id
                                                                        .name))

                                                                search_attrs = product_tmpl_attribute_value_obj.search(
                                                                    [('product_tmpl_id',
                                                                      '=',
                                                                      created_product_tmpl
                                                                      .id),
                                                                     ('product_attribute_value_id',
                                                                      '=',
                                                                      product_varient_attribute_value_id
                                                                      .
                                                                      product_attribute_value_id
                                                                      .id),
                                                                     ('attribute_id',
                                                                      '=',
                                                                      product_varient_attribute_value_id
                                                                      .
                                                                      attribute_id
                                                                      .id)],
                                                                    limit=1)

                                                                if search_attrs:
                                                                    search_attrs.write({
                                                                        'price_extra':
                                                                        extra_price,
                                                                    })
                                                # update price extra ends here

                                                if row[16] not in (None, ""):
                                                    var_vals.update({
                                                        'default_code':
                                                        row[16]
                                                    })

                                                if row[17] not in (None, ""):
                                                    var_vals.update(
                                                        {'barcode': row[17]})

                                                if row[18] not in (None, "",False,0,0.0,'0','0.0'):
                                                    var_vals.update(
                                                        {'weight': float(row[18])})

                                                if row[19] not in (None, "",False,0,0.0,'0','0.0'):
                                                    var_vals.update(
                                                        {'volume': float(row[19])})
                                                if row[23] not in (None, "",False,0,0.0,'0','0.0'):
                                                    var_vals.update({
                                                        'standard_price':
                                                        float(row[23])
                                                    })
                                                # ===========================================================
                                                # dynamic field logic start here
                                                # ===========================================================

                                                is_any_error_in_dynamic_field = False
                                                for k_row_index, v_field_dic in row_field_dic.items(
                                                ):

                                                    field_name = v_field_dic.get(
                                                        "name")
                                                    field_ttype = v_field_dic.get(
                                                        "ttype")
                                                    field_value = row[
                                                        k_row_index]
                                                    field_required = v_field_dic.get(
                                                        "required")
                                                    field_name_m2o = v_field_dic.get(
                                                        "name_m2o")

                                                    dic = self.validate_field_value(
                                                        field_name,
                                                        field_ttype,
                                                        field_value,
                                                        field_required,
                                                        field_name_m2o)
                                                    if dic.get("error", False):
                                                        skipped_line_no[str(
                                                            counter
                                                        )] = dic.get("error")
                                                        is_any_error_in_dynamic_field = True
                                                        break
                                                    else:
                                                        var_vals.update(dic)

                                                if is_any_error_in_dynamic_field:
                                                    counter = counter + 1
                                                    continue

                                                # ===========================================================
                                                # dynamic field logic start here
                                                # ===========================================================

                                                if product_varient.type == 'product' and row[
                                                        20] != '':
                                                    stock_vals = {
                                                        'product_tmpl_id':
                                                        created_product_tmpl.
                                                        id,
                                                        'new_quantity':
                                                        float(row[20]),
                                                        'product_id':
                                                        product_varient.id
                                                    }
                                                    created_qty_on_hand = self.env[
                                                        'stock.change.product.qty'].create(
                                                            stock_vals)
                                                    if created_qty_on_hand:
                                                        created_qty_on_hand.change_product_qty(
                                                        )

                                                if row[21].strip() not in (
                                                        None, ""):
                                                    image_path = row[21].strip(
                                                    )
                                                    if "http://" in image_path or "https://" in image_path:
                                                        try:
                                                            r = requests.get(
                                                                image_path)
                                                            if r and r.content:
                                                                image_base64 = base64.decodebytes(
                                                                    r.content)
                                                                var_vals.update({
                                                                    'image_1920':
                                                                    image_base64
                                                                })
                                                            else:
                                                                skipped_line_no[
                                                                    str(
                                                                        counter
                                                                    )] = " - URL not correct or check your image size. "
                                                                counter = counter + 1
                                                                continue
                                                        except Exception as e:
                                                            skipped_line_no[str(
                                                                counter
                                                            )] = " - URL not correct or check your image size " + ustr(
                                                                e)
                                                            counter = counter + 1
                                                            continue

                                                    else:
                                                        try:
                                                            with open(
                                                                    image_path,
                                                                    'rb'
                                                            ) as image:
                                                                image.seek(0)
                                                                binary_data = image.read(
                                                                )
                                                                image_base64 = codecs.encode(
                                                                    binary_data,
                                                                    'base64')
                                                                if image_base64:
                                                                    var_vals.update({
                                                                        'image_1920':
                                                                        image_base64
                                                                    })
                                                                else:
                                                                    skipped_line_no[
                                                                        str(
                                                                            counter
                                                                        )] = " - Could not find the image or please make sure it is accessible to this app. "
                                                                    counter = counter + 1
                                                                    continue
                                                        except Exception as e:
                                                            skipped_line_no[str(
                                                                counter
                                                            )] = " - Could not find the image or please make sure it is accessible to this app. " + ustr(
                                                                e)
                                                            counter = counter + 1
                                                            continue

                                                # code for if product variant have attributes and values
                                                barcode_list = []
                                                if row[22].strip() not in (
                                                        None, ""):
                                                    for x in row[22].split(
                                                            ','):
                                                        x = x.strip()
                                                        if x != '':
                                                            search_barcode = self.env[
                                                                'product.product'].search(
                                                                    [
                                                                        '|',
                                                                        ('barcode_line_ids.name',
                                                                         '=',
                                                                         x),
                                                                        ('barcode',
                                                                         '=',
                                                                         x)
                                                                    ],
                                                                    limit=1)
                                                            if not search_barcode:
                                                                barcode_vals = {
                                                                    'name': x
                                                                }
                                                                barcode_list.append(
                                                                    (0, 0,
                                                                     barcode_vals
                                                                     ))
                                                product_varient.barcode_line_ids = barcode_list

                                                product_varient.write(var_vals)

                                        elif self.method == 'write':

                                            # You have to search product by it's attributes and update its fields. do not create new proeduct.
                                            # Search Variants Here

                                            product_var_obj = self.env[
                                                'product.product']
                                            domain = []
                                            domain.append(
                                                ('product_tmpl_id', '=',
                                                 created_product_tmpl.id))

                                            for attr_value_id in attr_value_ids_list:
                                                domain.append((
                                                    'product_template_attribute_value_ids.product_attribute_value_id.id',
                                                    '=', attr_value_id))

                                            product_varient = product_var_obj.search(
                                                domain, limit=1)
                                            if not product_varient:

                                                if attr_value_ids_list and attr_ids_list:
                                                    i = 0
                                                    while i < len(
                                                            attr_ids_list):
                                                        search_attr_line = pro_attr_line_obj.search(
                                                            [
                                                                ('attribute_id',
                                                                 '=',
                                                                 attr_ids_list[
                                                                     i]),
                                                                ('product_tmpl_id',
                                                                 '=',
                                                                 created_product_tmpl
                                                                 .id),
                                                            ],
                                                            limit=1)
                                                        if search_attr_line:
                                                            past_values_list = []
                                                            past_values_list = search_attr_line.value_ids.ids
                                                            past_values_list.append(
                                                                attr_value_ids_list[
                                                                    i])
                                                            search_attr_line.write({
                                                                'value_ids':
                                                                [(6, 0,
                                                                  past_values_list
                                                                  )]
                                                            })
                                                        else:
                                                            pro_attr_line_obj.create({
                                                                'attribute_id':
                                                                attr_ids_list[
                                                                    i],
                                                                'value_ids':
                                                                [(6, 0, [
                                                                    attr_value_ids_list[
                                                                        i]
                                                                ])],
                                                                'product_tmpl_id':
                                                                created_product_tmpl
                                                                .id,
                                                            })
                                                        i += 1
                                                created_product_tmpl._create_variant_ids(
                                                )
                                                product_varient = product_var_obj.search(
                                                    domain, limit=1)

                                            if not product_varient:
                                                skipped_line_no[str(
                                                    counter
                                                )] = " - Product Variant not found. "
                                                counter = counter + 1
                                                continue

                                            # update price extra start here
                                            if attr_value_price_dic:
                                                product_tmpl_attribute_value_obj = self.env[
                                                    "product.template.attribute.value"]
                                                extra_price = 0
                                                for product_varient_attribute_value_id in product_varient.product_template_attribute_value_ids:
                                                    if attr_value_price_dic.get(
                                                            product_varient_attribute_value_id
                                                            .name, False):
                                                        extra_price = 0
                                                        if attr_value_price_dic.get(
                                                                product_varient_attribute_value_id
                                                                .name) not in [
                                                                    0, 0.0, '',
                                                                    "", None
                                                        ]:
                                                            extra_price = float(
                                                                attr_value_price_dic
                                                                .get(
                                                                    product_varient_attribute_value_id
                                                                    .name))

                                                            search_attrs = product_tmpl_attribute_value_obj.search(
                                                                [('product_tmpl_id',
                                                                  '=',
                                                                  created_product_tmpl
                                                                  .id),
                                                                 ('product_attribute_value_id',
                                                                  '=',
                                                                  product_varient_attribute_value_id
                                                                  .
                                                                  product_attribute_value_id
                                                                  .id),
                                                                 ('attribute_id',
                                                                  '=',
                                                                  product_varient_attribute_value_id
                                                                  .attribute_id
                                                                  .id)],
                                                                limit=1)

                                                            if search_attrs:
                                                                search_attrs.write({
                                                                    'price_extra':
                                                                    extra_price,
                                                                })
                                            # update price extra ends here

                                            if row[16] not in (None, ""):
                                                var_vals.update(
                                                    {'default_code': row[16]})

                                            if row[17] not in (None, ""):
                                                var_vals.update(
                                                    {'barcode': row[17]})

                                            if row[18] not in (None, "",False,0,0.0,'0','0.0'):
                                                var_vals.update(
                                                    {'weight': float(row[18])})

                                            if row[19] not in (None, "",False,0,0.0,'0','0.0'):
                                                var_vals.update(
                                                    {'volume': float(row[19])})
                                            if row[23] not in (None, "",False,0,0.0,'0','0.0'):
                                                var_vals.update({
                                                    'standard_price':
                                                    float(row[23])
                                                })
                                            # ===========================================================
                                            # dynamic field logic start here
                                            # ===========================================================

                                            is_any_error_in_dynamic_field = False
                                            for k_row_index, v_field_dic in row_field_dic.items(
                                            ):

                                                field_name = v_field_dic.get(
                                                    "name")
                                                field_ttype = v_field_dic.get(
                                                    "ttype")
                                                field_value = row[k_row_index]
                                                field_required = v_field_dic.get(
                                                    "required")
                                                field_name_m2o = v_field_dic.get(
                                                    "name_m2o")

                                                dic = self.validate_field_value(
                                                    field_name, field_ttype,
                                                    field_value,
                                                    field_required,
                                                    field_name_m2o)
                                                if dic.get("error", False):
                                                    skipped_line_no[str(
                                                        counter)] = dic.get(
                                                            "error")
                                                    is_any_error_in_dynamic_field = True
                                                    break
                                                else:
                                                    var_vals.update(dic)

                                            if is_any_error_in_dynamic_field:
                                                counter = counter + 1
                                                continue

                                            # ===========================================================
                                            # dynamic field logic start here
                                            # ===========================================================

                                            if product_varient.type == 'product' and row[
                                                    20] != '':
                                                stock_vals = {
                                                    'product_tmpl_id':
                                                    created_product_tmpl.id,
                                                    'new_quantity':
                                                    float(row[20]),
                                                    'product_id':
                                                    product_varient.id
                                                }
                                                created_qty_on_hand = self.env[
                                                    'stock.change.product.qty'].create(
                                                        stock_vals)
                                                if created_qty_on_hand:
                                                    created_qty_on_hand.change_product_qty(
                                                    )

                                            if row[21].strip() not in (None,
                                                                       ""):
                                                image_path = row[21].strip()
                                                if "http://" in image_path or "https://" in image_path:
                                                    try:
                                                        r = requests.get(
                                                            image_path)
                                                        if r and r.content:
                                                            image_base64 = base64.decodebytes(
                                                                r.content)
                                                            var_vals.update({
                                                                'image_1920':
                                                                image_base64
                                                            })
                                                        else:
                                                            skipped_line_no[str(
                                                                counter
                                                            )] = " - URL not correct or check your image size. "
                                                            counter = counter + 1
                                                            continue
                                                    except Exception as e:
                                                        skipped_line_no[str(
                                                            counter
                                                        )] = " - URL not correct or check your image size " + ustr(
                                                            e)
                                                        counter = counter + 1
                                                        continue

                                                else:
                                                    try:
                                                        with open(
                                                                image_path,
                                                                'rb') as image:
                                                            image.seek(0)
                                                            binary_data = image.read(
                                                            )
                                                            image_base64 = codecs.encode(
                                                                binary_data,
                                                                'base64')
                                                            if image_base64:
                                                                var_vals.update({
                                                                    'image_1920':
                                                                    image_base64
                                                                })
                                                            else:
                                                                skipped_line_no[
                                                                    str(
                                                                        counter
                                                                    )] = " - Could not find the image or please make sure it is accessible to this app. "
                                                                counter = counter + 1
                                                                continue
                                                    except Exception as e:
                                                        skipped_line_no[str(
                                                            counter
                                                        )] = " - Could not find the image or please make sure it is accessible to this app. " + ustr(
                                                            e)
                                                        counter = counter + 1
                                                        continue
                                            barcode_list = []
                                            if not self.update_existing:
                                                if row[22].strip() not in (
                                                        None, ""):
                                                    for x in row[22].split(
                                                            ','):
                                                        x = x.strip()
                                                        if x != '':
                                                            search_barcode = self.env[
                                                                'product.product'].search(
                                                                    [
                                                                        '|',
                                                                        ('barcode_line_ids.name',
                                                                         '=',
                                                                         x),
                                                                        ('barcode',
                                                                         '=',
                                                                         x)
                                                                    ],
                                                                    limit=1)
                                                            if not search_barcode:
                                                                self.env[
                                                                    'product.template.barcode'].sudo(
                                                                ).create({
                                                                    'name':
                                                                        x,
                                                                        'product_id':
                                                                        product_varient
                                                                        .id,
                                                                })
                                            else:
                                                product_varient.barcode_line_ids = False
                                                if row[22].strip() not in (
                                                        None, ""):
                                                    for x in row[22].split(
                                                            ','):
                                                        x = x.strip()
                                                        if x != '':
                                                            search_barcode = self.env[
                                                                'product.product'].search(
                                                                    [
                                                                        '|',
                                                                        ('barcode_line_ids.name',
                                                                         '=',
                                                                         x),
                                                                        ('barcode',
                                                                         '=',
                                                                         x)
                                                                    ],
                                                                    limit=1)
                                                            if not search_barcode:
                                                                barcode_vals = {
                                                                    'name': x
                                                                }
                                                                barcode_list.append(
                                                                    (0, 0,
                                                                     barcode_vals
                                                                     ))
                                            product_varient.barcode_line_ids = barcode_list
                                            product_varient.write(var_vals)

                                counter = counter + 1
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Name is empty. "
                                counter = counter + 1

                            
                            imported_lines += 1
                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid. " + ustr(e)
                            counter = counter + 1
                            continue
                    # For Loop Ends here
                    # TODO: NEED TO CLEAN LAST PRODUCT ALSO.
                    if created_product_tmpl and self.method == 'write':

                        # Remove Unnecessary Attribute Line.
                        # ===============================================
                        attrs = created_product_tmpl.attribute_line_ids.mapped(
                            'attribute_id').filtered(
                                lambda r: r.id not in list_to_keep_attr)
                        for attr in attrs:
                            line = created_product_tmpl.attribute_line_ids.search(
                                [
                                    ('attribute_id', '=', attr.id),
                                    ('product_tmpl_id', '=',
                                     created_product_tmpl.id),
                                ],
                                limit=1)
                            if line:
                                line.unlink()

                        # Remove Unnecessary Attribute Line.
                        # ===============================================

                        # Remove Unnecessary Attribute Value From Line.
                        # ===============================================
                        attr_values = created_product_tmpl.attribute_line_ids.mapped(
                            'value_ids').filtered(
                                lambda r: r.id not in list_to_keep_attr_value)
                        for attr_value in attr_values:
                            line = created_product_tmpl.attribute_line_ids.search(
                                [
                                    ('value_ids', 'in', attr_value.ids),
                                    ('product_tmpl_id', '=',
                                     created_product_tmpl.id),
                                ],
                                limit=1)
                            if line:
                                line.write({
                                    'value_ids': [(3, attr_value.id, 0)],
                                })

                        # Remove Unnecessary Attribute Value From Line.
                        # ===============================================

                        created_product_tmpl._create_variant_ids()
                        list_to_keep_attr = []
                        list_to_keep_attr_value = []
                except Exception as e:
                    raise UserError(
                        _("Sorry, Your csv or excel file does not match with our format"
                          + ustr(e)))
                # if length_reader == self.total_done_tmpl_var_mb:
                #     if not skipped_line_no:
                #         self.create_logs(
                #             self.total_done_tmpl_var_mb, skipped_line_no,0)
                #         self.state = 'done'
                if counter > 1:               
                    completed_records = (counter - len(skipped_line_no)) - 1
                #     if not skipped_line_no:
                #         self.create_store_logs(
                #             completed_records, skipped_line_no)
                #         self.state = 'done'
                #     else:
                #         self.received_error = True
                #         self.create_store_logs(
                #             completed_records, skipped_line_no)
                #         if self.on_error == 'break':
                #             self.state = 'error'
                #         elif self.import_limit == 0:
                #             if self.received_error:
                #                 self.state = 'partial_done'
                #             else:
                #                 self.state = 'done'
                    if not skipped_line_no:
                        self.create_product_var_mb_logs(
                            completed_records, skipped_line_no,imported_lines)
                        # if self.received_error:
                        #     self.state = 'partial_done'
                        # else:
                        self.state = 'done' if length_reader == self.total_done_tmpl_var_mb else 'running'
                    else:
                        self.received_error = True
                        self.create_product_var_mb_logs(
                            completed_records, skipped_line_no,imported_lines)
                        if self.on_error == 'break':
                            self.state = 'error'
                        elif self.import_limit == 0:
                            if self.received_error:
                                self.state = 'partial_done'
                            else:
                                self.state = 'done' if length_reader == self.total_done_tmpl_var_mb else None
