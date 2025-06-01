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

    def check_sh_import_payment(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_payment':
            value = True
        return value

    sh_import_payment_type = fields.Selection(related='base_id.sh_import_payment_type',readonly=False, string="Import File Type", required=True)
    sh_import_payment_is_create_partner = fields.Boolean(related='base_id.sh_import_payment_is_create_partner',readonly=False,string='Create Customer/Vendor ?')
    sh_import_payment_is_confirm_payment = fields.Boolean(related='base_id.sh_import_payment_is_confirm_payment',readonly=False,string='Confirm/Posted Payment ?')
    sh_import_payment_partner_by = fields.Selection(related='base_id.sh_import_payment_partner_by',readonly=False, string='Partner By')
    sh_import_payment_boolean = fields.Boolean(
        "Import Payments Boolean", default=check_sh_import_payment)
    sh_company_id_payment = fields.Many2one(
        related="base_id.sh_company_id_payment", readonly=False, string="Company", required=True)

    def create_logs(self, counter, skipped_line_no,confirm_records):
        dic_msg = str(counter) + " Records imported successfully"+"\n"
        dic_msg = dic_msg + str(confirm_records) + " Records Confirm"
        if skipped_line_no:
            dic_msg = dic_msg + "\nNote:"
        for k, v in skipped_line_no.items():
            dic_msg = dic_msg + "\nRow No " + k + " " + v + " "
        self.env['sh.import.log'].create({
            'message': dic_msg,
            'datetime': datetime.now(),
            'sh_store_id': self.id
        })

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
            name_relational_model = self.env['account.payment'].fields_get()[
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
            name_relational_model = self.env['account.payment'].fields_get()[
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

        #get selection field key and value.
        selection_key_value_list = self.env['account.payment'].sudo(
        )._fields[field_name].selection
        if selection_key_value_list and field_value not in (None, ""):
            for tuple_item in selection_key_value_list:
                if tuple_item[1] == field_value:
                    return {field_name: tuple_item[0] or False}

            return {"error": " - " + field_name + " given value " + str(field_value) + " does not match for selection. "}

        #finaly return false
        if field_value in (None, ""):
            return {field_name: False}

        return {field_name: field_value or False}

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
        if record.base_id.sh_technical_name == 'sh_import_payment':
            self.import_payment(record)
        return res

    def import_payment(self,record):
        self = record
        account_payment_obj = self.env['account.payment']
        ir_model_fields_obj = self.env['ir.model.fields']

        # # perform import SO
        if self and self.sh_file:

            if self.sh_import_payment_type == 'csv' or self.sh_import_payment_type == 'excel':
                counter = 1
                skipped_line_no = {}
                count=0
                row_field_dic = {}
                row_field_error_dic = {}
                created_payment_list_for_confirm = []
                created_payment_list = []
                try:
                    if self.sh_import_payment_type == 'csv':
                        sh_file = str(base64.decodebytes(
                            self.sh_file).decode('utf-8'))
                        length_r = csv.reader(sh_file.splitlines())
                        length_reader = len(list(length_r))
                        myreader = csv.reader(sh_file.splitlines())
                        myreader = list(myreader)                       
                    elif self.sh_import_payment_type == 'excel':
                        myreader=self.read_xls_book()                       
                        length_reader = len(myreader)

                    skip_header = True
                    till = length_reader
                    created_payment = False
                    
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
                                for i in range(9, len(row)):
                                    name_field = row[i]
                                    name_m2o = False
                                    if '@' in row[i]:
                                        list_field_str = name_field.split('@')
                                        name_field = list_field_str[0]
                                        name_m2o = list_field_str[1]
                                    search_field = ir_model_fields_obj.sudo().search([
                                        ("model", "=", "account.payment"),
                                        ("name", "=", name_field),
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
                            vals = {'company_id': self.sh_company_id_payment.id,
                                    'state': 'draft'}
                            partner_id = False
                            if row[0].strip() not in ("", None, False):
                                payment_type = ''
                                if row[0].strip() == 'Send Money':
                                    payment_type = 'outbound'
                                elif row[0].strip() == 'Receive Money':
                                    payment_type = 'inbound'
                                if payment_type:
                                    vals.update({
                                        'payment_type': payment_type
                                    })
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Payment type is empty. "
                                counter = counter + 1
                                continue
                            if row[1].strip() not in ("", None, False):
                                partner_type = ''
                                if row[1].strip() == 'Customer':
                                    partner_type = 'customer'
                                elif row[1].strip() == 'Vendor':
                                    partner_type = 'supplier'
                                if partner_type:
                                    vals.update({
                                        'partner_type': partner_type
                                    })
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Partner type is empty. "
                                counter = counter + 1
                                continue
                            if row[2].strip() not in ("", None, False):
                                partner_by = 'name'
                                if self.sh_import_payment_partner_by == 'id':
                                    partner_by = 'id'
                                    if int(row[2].strip())>0:
                                        partner_id = self.env['res.partner'].sudo().search(
                                        [(partner_by, '=', row[2].strip())], limit=1)
                                elif self.sh_import_payment_partner_by == 'name':
                                    partner_by = 'name'
                                elif self.sh_import_payment_partner_by == 'email':
                                    partner_by = 'email'
                                elif self.sh_import_payment_partner_by == 'mobile':
                                    partner_by = 'mobile'
                                elif self.sh_import_payment_partner_by == 'phone':
                                    partner_by = 'phone'
                                elif self.sh_import_payment_partner_by == 'ref':
                                    partner_by = 'ref'
                                if self.sh_import_payment_partner_by != 'id': 
                                    partner_id = self.env['res.partner'].sudo().search(
                                        [(partner_by, '=', row[2].strip())], limit=1)
                                if not partner_id:
                                    if self.sh_import_payment_is_create_partner:
                                        partner_id = self.env['res.partner'].create({'company_type': 'person',
                                                                                     'name': row[2].strip(),
                                                                                     'customer_rank': 1,
                                                                                     'supplier_rank': 1,
                                                                                     })
                                if partner_id:
                                    vals.update({
                                        'partner_id': partner_id.id
                                    })
                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Partner not found. "
                                    counter = counter + 1
                                    continue
                            partner_type = ''
                            if row[1].strip() == 'Customer':
                                partner_type = 'customer'
                            elif row[1].strip() == 'Vendor':
                                partner_type = 'supplier'
                            if row[3].strip() not in ("", None, False):
                                account_code = self.env['account.account'].sudo().search(
                                    [('code', '=', row[3].strip()), ('company_id', '=', self.sh_company_id_payment.id)], limit=1)
                                if account_code:
                                    vals.update({
                                        'destination_account_id': account_code.id
                                    })
                                else:
                                    if partner_type == 'customer':
                                        if partner_id:
                                            vals.update({
                                                'destination_account_id': partner_id.with_company(self.sh_company_id_payment).property_account_receivable_id.id
                                            })
                                        else:
                                            account_id = self.env['account.account'].search([
                                                ('company_id', '=',
                                                 self.sh_company_id_payment.id),
                                                ('internal_type',
                                                 '=', 'receivable'),
                                                ('deprecated', '=', False),
                                            ], limit=1)
                                            vals.update({
                                                'destination_account_id': account_id.id
                                            })
                                    elif partner_type == 'supplier':
                                        if partner_id:
                                            vals.update({
                                                'destination_account_id': partner_id.with_company(self.sh_company_id_payment).property_account_payable_id.id
                                            })
                                        else:
                                            account_id = self.env['account.account'].search([
                                                ('company_id', '=',
                                                 self.sh_company_id_payment.id),
                                                ('internal_type', '=', 'payable'),
                                                ('deprecated', '=', False),
                                            ], limit=1)
                                            vals.update({
                                                'destination_account_id': account_id.id
                                            })
                            else:
                                if partner_type == 'customer':
                                    if partner_id:
                                        vals.update({
                                            'destination_account_id': partner_id.with_company(self.sh_company_id_payment).property_account_receivable_id.id
                                        })
                                    elif not partner_id:
                                        account_id = self.env['account.account'].search([
                                            ('company_id', '=',
                                             self.sh_company_id_payment.id),
                                            ('internal_type', '=', 'receivable'),
                                            ('deprecated', '=', False),
                                        ], limit=1)
                                        vals.update({
                                            'destination_account_id': account_id.id
                                        })
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Account not found. "
                                        counter = counter + 1
                                        continue
                                elif partner_type == 'supplier':
                                    if partner_id:
                                        vals.update({
                                            'destination_account_id': partner_id.with_company(self.sh_company_id_payment).property_account_payable_id.id
                                        })
                                    elif not partner_id:
                                        account_id = self.env['account.account'].search([
                                            ('company_id', '=',
                                             self.sh_company_id_payment.id),
                                            ('internal_type', '=', 'payable'),
                                            ('deprecated', '=', False),
                                        ], limit=1)
                                        vals.update({
                                            'destination_account_id': account_id.id
                                        })
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Account not found. "
                                        counter = counter + 1
                                        continue
                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Account not found. "
                                    counter = counter + 1
                                    continue
                            if row[4].strip() not in ("", None, False):
                                journal_id = self.env['account.journal'].sudo().search(
                                    [('name', '=', row[4].strip())], limit=1)
                                if journal_id:
                                    vals.update({
                                        'journal_id': journal_id.id
                                    })
                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Journal not found. "
                                    counter = counter + 1
                                    continue
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Journal is empty. "
                                counter = counter + 1
                                continue
                            if row[5].strip() not in ("", None, False):
                                cd = row[5].strip()
                                cd = str(datetime.strptime(
                                    cd, DEFAULT_SERVER_DATE_FORMAT).date())
                                vals.update({'date': cd})
                            else:
                                vals.update({'date': fields.Date.today()})
                            if row[6].strip() not in ("", None, False):
                                vals.update({'ref': row[6].strip()})
                            if row[7].strip() not in ("", None, False):
                                vals.update({'amount': float(row[7].strip())})
                            else:
                                vals.update({'amount': 0.0})
                            if row[8].strip() not in ("", None, False):
                                currency_id = self.env['res.currency'].sudo().search(
                                    [('name', '=', row[8].strip())], limit=1)
                                if currency_id:
                                    vals.update(
                                        {'currency_id': currency_id.id})
                                else:
                                    vals.update(
                                        {'currency_id': self.env.company.currency_id.id})
                            else:
                                vals.update(
                                    {'currency_id': self.env.company.currency_id.id})
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

                            if vals:
                                created_payment = account_payment_obj.sudo().create(vals)
                                created_payment_list_for_confirm.append(
                                    created_payment.id)
                                created_payment_list.append(created_payment.id)
                                counter = counter + 1
                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid. " + ustr(e)
                            counter = counter + 1
                            continue
                    if created_payment_list_for_confirm and self.sh_import_payment_is_confirm_payment:
                        payments = account_payment_obj.search(
                            [('id', 'in', created_payment_list_for_confirm)])
                        if payments:
                            for payment in payments:
                                payment.action_post()
                    else:
                        created_payment_list_for_confirm = []
                except Exception as e:
                    raise UserError(
                        _("Sorry, Your csv or excel file does not match with our format"
                        + ustr(e)))
                if counter > 1:
                    completed_records = len(created_payment_list)
                    confirm_records = len(created_payment_list_for_confirm)
                    if not skipped_line_no:
                        self.create_logs(
                            completed_records, skipped_line_no,confirm_records)
                        self.state = 'done'
                    else:
                        self.received_error = True
                        self.create_logs(
                            completed_records, skipped_line_no,confirm_records)
                        if self.on_error == 'break':
                            self.state = 'error'
                        elif self.import_limit == 0:
                            if self.received_error:
                                self.state = 'partial_done'
                            else:
                                self.state = 'done'
