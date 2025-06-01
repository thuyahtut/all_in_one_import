# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
from odoo.tools import ustr
import logging

_logger = logging.getLogger(__name__)


class ImportCOA(models.TransientModel):
    _name = "sh.import.coa"
    _description = 'Import Chart Of Account'

    import_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    file = fields.Binary(string="File", required=True)

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
            name_relational_model = self.env['account.account'].fields_get()[
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
            name_relational_model = self.env['account.account'].fields_get()[
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
        selection_key_value_list = self.env['account.account'].sudo(
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

    def show_success_msg(self, counter, skipped_line_no):
        # open the new success message box
        view = self.env.ref('sh_message.sh_message_wizard')
        context = dict(self._context or {})
        dic_msg = str(counter) + " Records imported successfully \n"
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

    def import_coa_apply(self):

        account_obj = self.env['account.account']
        ir_model_fields_obj = self.env['ir.model.fields']
        # perform import lead
        if self and self.file:
            # For CSV
            if self.import_type == 'csv':
                counter = 1
                skipped_line_no = {}
                row_field_dic = {}
                row_field_error_dic = {}
                try:
                    file = str(base64.decodebytes(self.file).decode('utf-8'))
                    myreader = csv.reader(file.splitlines())
                    skip_header = True

                    for row in myreader:
                        try:
                            if skip_header:
                                skip_header = False
                                for i in range(8, len(row)):
                                    name_field = row[i]
                                    name_m2o = False
                                    if '@' in row[i]:
                                        list_field_str = name_field.split('@')
                                        name_field = list_field_str[0]
                                        name_m2o = list_field_str[1]
                                    search_field = ir_model_fields_obj.sudo().search([
                                        ("model", "=", "account.account"),
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

                                counter = counter + 1
                                continue

                            if row_field_error_dic:
                                res = self.show_success_msg(
                                    0, row_field_error_dic)
                                return res
                            if row[0] not in ("", None):                                
                                code = row[0]
                                domain = [('code', '=', code)]
                                already_account = self.env['account.account'].search(
                                    domain)
                                if already_account:
                                    skipped_line_no[str(
                                        counter)] = " - Account Code Already Exists. "
                                    counter = counter + 1
                                    continue
                            vals = {'company_id': self.env.company.id}
                            if row[0] not in ("", None):
                                vals.update({
                                    'code': row[0]
                                })
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Code is empty. "
                                counter = counter + 1
                                continue
                            if row[1] not in ("", None):
                                vals.update({
                                    'name': row[1]
                                })
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Name is empty. "
                                counter = counter + 1
                                continue
                            if row[2] not in ("", None):
                                if row[2] == 'Receivable':
                                    row[2] = 'asset_receivable'
                                elif row[2] == 'Bank and Cash':
                                    row[2] = 'asset_cash'
                                elif row[2] == 'Current Assets':
                                    row[2] = 'asset_current'
                                elif row[2] == 'Non-current Assets':
                                    row[2] = 'asset_non_current'
                                elif row[2] == 'Prepayments':
                                    row[2] = 'asset_prepayments'
                                elif row[2] == 'Fixed Assets':
                                    row[2] = 'asset_fixed'
                                elif row[2] == 'Payable':
                                    row[2] = 'liability_payable'
                                elif row[2] == 'Credit Card':
                                    row[2] = 'liability_credit_card'
                                elif row[2] == 'Current Liabilities':
                                    row[2] = 'liability_current'
                                elif row[2] == 'Non-current Liabilities':
                                    row[2] = 'liability_non_current'
                                elif row[2] == 'Equity':
                                    row[2] = 'equity'
                                elif row[2] == 'Current Year Earnings':
                                    row[2] = 'equity_unaffected'
                                elif row[2] == 'Income':
                                    row[2] = 'income'
                                elif row[2] == 'Other Income':
                                    row[2] = 'income_other'
                                elif row[2] == 'Expenses':
                                    row[2] = 'expense'
                                elif row[2] == 'Depreciation':
                                    row[2] = 'expense_depreciation'
                                elif row[2] == 'Cost of Revenue':
                                    row[2] = 'expense_direct_cost'
                                elif row[2] == 'Off-Balance Sheet':
                                    row[2] = 'off_balance'                               
                                vals.update({
                                    'account_type': row[2]
                                })
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Type is empty."
                                counter = counter + 1
                                continue
                            if row[3] not in ("", None):
                                taxes_list = []
                                for x in row[3].split(','):
                                    x = x.strip()
                                    if x != '':
                                        search_tax = self.env['account.tax'].search(
                                            [('name', '=', x)], limit=1)
                                        if search_tax:
                                            taxes_list.append(
                                                search_tax.id)
                                vals.update(
                                    {'tax_ids': [(6, 0, taxes_list)]})
                            if row[4] not in ("", None):
                                tag_list = []
                                for x in row[4].split(','):
                                    x = x.strip()
                                    if x != '':
                                        search_tag = self.env['account.account.tag'].search(
                                            [('name', '=', x)], limit=1)
                                        if search_tag:
                                            tag_list.append(
                                                search_tag.id)
                                vals.update(
                                    {'tag_ids': [(6, 0, tag_list)]})
                            if row[5] not in ("", None):
                                if row[5].strip() == 'FALSE':
                                    vals.update({
                                        'reconcile': False
                                    })
                                elif row[5].strip() == 'TRUE':
                                    vals.update({
                                        'reconcile': True
                                    })
                            if row[6] not in ("", None):
                                if row[6].strip() == 'FALSE':
                                    vals.update({
                                        'deprecated': False
                                    })
                                elif row[6].strip() == 'TRUE':
                                    vals.update({
                                        'deprecated': True
                                    })
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

                            account_obj.create(vals)
                            counter = counter + 1

                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid " + ustr(e)
                            counter = counter + 1
                            continue

                except Exception:
                    raise UserError(
                        _("Sorry, Your csv file does not match with our format"))

                if counter > 1:
                    completed_account = (counter - len(skipped_line_no)) - 2
                    res = self.show_success_msg(
                        completed_account, skipped_line_no)
                    return res

#             # For Excel
            if self.import_type == 'excel':
                counter = 1
                skipped_line_no = {}
                row_field_dic = {}
                row_field_error_dic = {}
                try:
                    wb = xlrd.open_workbook(
                        file_contents=base64.decodebytes(self.file))
                    sheet = wb.sheet_by_index(0)
                    skip_header = True
                    for row in range(sheet.nrows):
                        try:
                            if skip_header:
                                skip_header = False
                                for i in range(8, sheet.ncols):
                                    name_field = sheet.cell(row, i).value
                                    name_m2o = False
                                    if '@' in sheet.cell(row, i).value:
                                        list_field_str = name_field.split('@')
                                        name_field = list_field_str[0]
                                        name_m2o = list_field_str[1]
                                    search_field = ir_model_fields_obj.sudo().search([
                                        ("model", "=", "account.account"),
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
                                            {sheet.cell(row, i).value: " - field not found"})

                                counter = counter + 1
                                continue

                            if row_field_error_dic:
                                res = self.show_success_msg(
                                    0, row_field_error_dic)
                                return res
                            if sheet.cell(row, 0).value not in ("", None):
                                if isinstance(sheet.cell(row, 0).value, float):
                                    code = int(sheet.cell(row, 0).value)
                                    domain = [('code', '=', code)]
                                    already_account = self.env['account.account'].search(
                                        domain)
                                    if already_account:
                                        skipped_line_no[str(
                                            counter)] = " - Account Code Already Exists. "
                                        counter = counter + 1
                                        continue
                            vals = {'company_id': self.env.company.id}
                            if sheet.cell(row, 0).value not in ("", None):
                                if isinstance(sheet.cell(row, 0).value, float):
                                    code = int(sheet.cell(row, 0).value)
                                    code_str = str(code)
                                    vals.update({
                                        'code': code_str
                                    })
                                else:
                                    vals.update({
                                        'code': sheet.cell(row, 0).value
                                    })
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Code is empty. "
                                counter = counter + 1
                                continue
                            if sheet.cell(row, 1).value not in ("", None):
                                vals.update({
                                    'name': sheet.cell(row, 1).value
                                })
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Name is empty. "
                                counter = counter + 1
                                continue
                            if sheet.cell(row, 2).value not in ("", None):
                                ans =''
                                if sheet.cell(row, 2).value == 'Receivable':
                                    ans = 'asset_receivable'
                                elif sheet.cell(row, 2).value == 'Bank and Cash':
                                    ans = 'asset_cash'
                                elif sheet.cell(row, 2).value == 'Current Assets':
                                    ans = 'asset_current'
                                elif sheet.cell(row, 2).value == 'Non-current Assets':
                                    ans = 'asset_non_current'
                                elif sheet.cell(row, 2).value == 'Prepayments':
                                    ans= 'asset_prepayments'
                                elif sheet.cell(row, 2).value == 'Fixed Assets':
                                    ans = 'asset_fixed'
                                elif sheet.cell(row, 2).value == 'Payable':
                                    ans = 'liability_payable'
                                elif sheet.cell(row, 2).value == 'Credit Card':
                                    ans = 'liability_credit_card'
                                elif sheet.cell(row, 2).value == 'Current Liabilities':
                                    ans = 'liability_current'
                                elif sheet.cell(row, 2).value == 'Non-current Liabilities':
                                    ans = 'liability_non_current'
                                elif sheet.cell(row, 2).value == 'Equity':
                                    ans = 'equity'
                                elif sheet.cell(row, 2).value == 'Current Year Earnings':
                                    ans = 'equity_unaffected'
                                elif sheet.cell(row, 2).value == 'Income':
                                    ans = 'income'
                                elif sheet.cell(row, 2).value == 'Other Income':
                                    ans = 'income_other'
                                elif sheet.cell(row, 2).value == 'Expenses':
                                    ans = 'expense'
                                elif sheet.cell(row, 2).value == 'Depreciation':
                                    ans = 'expense_depreciation'
                                elif sheet.cell(row, 2).value == 'Cost of Revenue':
                                    ans = 'expense_direct_cost'
                                elif sheet.cell(row, 2).value == 'Off-Balance Sheet':
                                   ans = 'off_balance'                               
                                vals.update({
                                    'account_type': ans
                                })
                            else:
                                skipped_line_no[str(
                                    counter)] = " - Type is empty."
                                counter = counter + 1
                                continue
                            if sheet.cell(row, 3).value not in ("", None):
                                taxes_list = []
                                for x in sheet.cell(row, 3).value.split(','):
                                    x = x.strip()
                                    if x != '':
                                        search_tax = self.env['account.tax'].search(
                                            [('name', '=', x)], limit=1)
                                        if search_tax:
                                            taxes_list.append(
                                                search_tax.id)
                                vals.update(
                                    {'tax_ids': [(6, 0, taxes_list)]})
                            if sheet.cell(row, 4).value not in ("", None):
                                tag_list = []
                                for x in sheet.cell(row, 4).value.split(','):
                                    x = x.strip()
                                    if x != '':
                                        search_tag = self.env['account.account.tag'].search(
                                            [('name', '=', x)], limit=1)
                                        if search_tag:
                                            tag_list.append(
                                                search_tag.id)
                                vals.update(
                                    {'tag_ids': [(6, 0, tag_list)]})
                            if sheet.cell(row, 5).value not in ("", None):
                                if sheet.cell(row, 5).value.strip() == 'FALSE':
                                    vals.update({
                                        'reconcile': False
                                    })
                                elif sheet.cell(row, 5).value.strip() == 'TRUE':
                                    vals.update({
                                        'reconcile': True
                                    })
                            if sheet.cell(row, 6).value not in ("", None):
                                if sheet.cell(row, 6).value.strip() == 'FALSE':
                                    vals.update({
                                        'deprecated': False
                                    })
                                elif sheet.cell(row, 6).value.strip() == 'TRUE':
                                    vals.update({
                                        'deprecated': True
                                    })
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

                            account_obj.create(vals)
                            counter = counter + 1

                        except Exception as e:
                            skipped_line_no[str(
                                counter)] = " - Value is not valid " + ustr(e)
                            counter = counter + 1
                            continue

                except Exception:
                    raise UserError(
                        _("Sorry, Your excel file does not match with our format"))

                if counter > 1:
                    completed_account = (counter - len(skipped_line_no)) - 2
                    res = self.show_success_msg(
                        completed_account, skipped_line_no)
                    return res
