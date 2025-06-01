# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, api, _
from odoo.exceptions import UserError
import csv
import base64
import xlrd
from odoo.tools import ustr
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class ImportPaymentWizard(models.TransientModel):
    _name = "sh.import.payment"
    _description = "Import Payment"

    @api.model
    def get_deafult_company(self):
        company_id = self.env.company
        return company_id

    import_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    file = fields.Binary(string="File", required=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, default=get_deafult_company)
    is_create_partner = fields.Boolean('Create Customer/Vendor ?')
    is_confirm_payment = fields.Boolean('Confirm/Posted Payment ?')
    partner_by = fields.Selection([('id', 'Database ID'), ('name', 'Name'), ('email', 'Email'), (
        'mobile', 'Mobile'), ('phone', 'Phone'), ('ref', 'Reference')], string='Partner By', default='name')

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

    def show_success_msg(self, counter, confirm_rec, skipped_line_no):
        # open the new success message box
        view = self.env.ref('sh_message.sh_message_wizard')
        context = dict(self._context or {})
        dic_msg = str(counter) + " Records imported successfully \n"
        dic_msg = dic_msg + str(confirm_rec) + " Records Validate"
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

    def import_payment_apply(self):
        account_payment_obj = self.env['account.payment']
        ir_model_fields_obj = self.env['ir.model.fields']
        if self and self.file:
            if self.import_type == 'csv':
                counter = 1
                skipped_line_no = {}
                row_field_dic = {}
                row_field_error_dic = {}
                try:
                    file = str(base64.decodebytes(self.file).decode('utf-8'))
                    myreader = csv.reader(file.splitlines())
                    skip_header = True
                    created_payment = False
                    created_payment_list_for_confirm = []
                    created_payment_list = []
                    for row in myreader:
                        try:
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

                                counter = counter + 1
                                continue

                            if row_field_error_dic:
                                res = self.show_success_msg(
                                    0, row_field_error_dic)
                                return res
                            vals = {'company_id': self.company_id.id,
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
                                if self.partner_by == 'id':
                                    partner_by = 'id'
                                    if int(row[2].strip())>0:
                                        partner_id = self.env['res.partner'].sudo().search(
                                        [(partner_by, '=', row[2].strip())], limit=1)
                                elif self.partner_by == 'name':
                                    partner_by = 'name'
                                elif self.partner_by == 'email':
                                    partner_by = 'email'
                                elif self.partner_by == 'mobile':
                                    partner_by = 'mobile'
                                elif self.partner_by == 'phone':
                                    partner_by = 'phone'
                                elif self.partner_by == 'ref':
                                    partner_by = 'ref'
                                if self.partner_by != 'id': 
                                    partner_id = self.env['res.partner'].sudo().search(
                                        [(partner_by, '=', row[2].strip())], limit=1)
                                if not partner_id:
                                    if self.is_create_partner:
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
                                    [('code', '=', row[3].strip()), ('company_id', '=', self.company_id.id)], limit=1)
                                if account_code:
                                    vals.update({
                                        'destination_account_id': account_code.id
                                    })
                                else:
                                    if partner_type == 'customer':
                                        if partner_id:
                                            vals.update({
                                                'destination_account_id': partner_id.with_company(self.company_id).property_account_receivable_id.id
                                            })
                                        else:
                                            account_id = self.env['account.account'].search([
                                                ('company_id', '=',
                                                 self.company_id.id),
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
                                                'destination_account_id': partner_id.with_company(self.company_id).property_account_payable_id.id
                                            })
                                        else:
                                            account_id = self.env['account.account'].search([
                                                ('company_id', '=',
                                                 self.company_id.id),
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
                                            'destination_account_id': partner_id.with_company(self.company_id).property_account_receivable_id.id
                                        })
                                    elif not partner_id:
                                        account_id = self.env['account.account'].search([
                                            ('company_id', '=',
                                             self.company_id.id),
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
                                            'destination_account_id': partner_id.with_company(self.company_id).property_account_payable_id.id
                                        })
                                    elif not partner_id:
                                        account_id = self.env['account.account'].search([
                                            ('company_id', '=',
                                             self.company_id.id),
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
                                    cd, '%Y-%m-%d').date())
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
                                counter)] = " - Value is not valid " + ustr(e)
                            counter = counter + 1
                            continue
                    if created_payment_list_for_confirm and self.is_confirm_payment:
                        payments = account_payment_obj.search(
                            [('id', 'in', created_payment_list_for_confirm)])
                        if payments:
                            for payment in payments:
                                payment.action_post()
                    else:
                        created_payment_list_for_confirm = []
                except Exception:
                    raise UserError(
                        _("Sorry, Your csv file does not match with our format"))

                if counter > 1:
                    completed_records = len(created_payment_list)
                    confirm_rec = len(created_payment_list_for_confirm)
                    res = self.show_success_msg(
                        completed_records, confirm_rec, skipped_line_no)
                    return res

            elif self.import_type == 'excel':
                counter = 1
                skipped_line_no = {}
                row_field_dic = {}
                row_field_error_dic = {}
                try:
                    wb = xlrd.open_workbook(
                        file_contents=base64.decodebytes(self.file))
                    sheet = wb.sheet_by_index(0)
                    skip_header = True
                    created_payment = False
                    created_payment_list_for_confirm = []
                    created_payment_list = []
                    for row in range(sheet.nrows):
                        try:
                            if skip_header:
                                skip_header = False
                                for i in range(9, sheet.ncols):
                                    name_field = sheet.cell(row, i).value
                                    name_m2o = False
                                    if '@' in sheet.cell(row, i).value:
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
                                            {sheet.cell(row, i).value: " - field not found"})
                                counter = counter + 1
                                continue
                            if row_field_error_dic:
                                res = self.show_success_msg(
                                    0, row_field_error_dic)
                                return res
                            vals = {'company_id': self.company_id.id,
                                    'state': 'draft'}
                            partner_id = False
                            if sheet.cell(row, 0).value.strip() not in ("", None, False):
                                payment_type = ''
                                if sheet.cell(row, 0).value.strip() == 'Send Money':
                                    payment_type = 'outbound'
                                elif sheet.cell(row, 0).value.strip() == 'Receive Money':
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
                            if sheet.cell(row, 1).value.strip() not in ("", None, False):
                                partner_type = ''
                                if sheet.cell(row, 1).value.strip() == 'Customer':
                                    partner_type = 'customer'
                                elif sheet.cell(row, 1).value.strip() == 'Vendor':
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
                            if sheet.cell(row, 2).value.strip() not in ("", None, False):
                                partner_by = 'name'
                                if self.partner_by == 'id':
                                    partner_by = 'id'
                                    if int(sheet.cell(row, 2).value.strip())>0:
                                        partner_id = self.env['res.partner'].sudo().search(
                                        [(partner_by, '=', sheet.cell(row, 2).value.strip())], limit=1)
                                elif self.partner_by == 'name':
                                    partner_by = 'name'
                                elif self.partner_by == 'email':
                                    partner_by = 'email'
                                elif self.partner_by == 'mobile':
                                    partner_by = 'mobile'
                                elif self.partner_by == 'phone':
                                    partner_by = 'phone'
                                elif self.partner_by == 'ref':
                                    partner_by = 'ref'
                                if self.partner_by != 'id': 
                                    partner_id = self.env['res.partner'].sudo().search(
                                        [(partner_by, '=', sheet.cell(row, 2).value.strip())], limit=1)
                                if not partner_id:
                                    if self.is_create_partner:
                                        partner_id = self.env['res.partner'].create({'company_type': 'person',
                                                                                     'name': sheet.cell(row, 2).value.strip(),
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
                            if sheet.cell(row, 1).value.strip() == 'Customer':
                                partner_type = 'customer'
                            elif sheet.cell(row, 1).value.strip() == 'Vendor':
                                partner_type = 'supplier'
                            if sheet.cell(row, 3).value.strip() not in ("", None, False):
                                account_code = self.env['account.account'].sudo().search([('code', '=', sheet.cell(
                                    row, 3).value.strip()), ('company_id', '=', self.company_id.id)], limit=1)
                                if account_code:
                                    vals.update({
                                        'destination_account_id': account_code.id
                                    })
                                else:
                                    if partner_type == 'customer':
                                        if partner_id:
                                            vals.update({
                                                'destination_account_id': partner_id.with_company(self.company_id).property_account_receivable_id.id
                                            })
                                        else:
                                            account_id = self.env['account.account'].search([
                                                ('company_id', '=',
                                                 self.company_id.id),
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
                                                'destination_account_id': partner_id.with_company(self.company_id).property_account_payable_id.id
                                            })
                                        else:
                                            account_id = self.env['account.account'].search([
                                                ('company_id', '=',
                                                 self.company_id.id),
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
                                            'destination_account_id': partner_id.with_company(self.company_id).property_account_receivable_id.id
                                        })
                                    elif not partner_id:
                                        account_id = self.env['account.account'].search([
                                            ('company_id', '=',
                                             self.company_id.id),
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
                                            'destination_account_id': partner_id.with_company(self.company_id).property_account_payable_id.id
                                        })
                                    elif not partner_id:
                                        account_id = self.env['account.account'].search([
                                            ('company_id', '=',
                                             self.company_id.id),
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
                            if sheet.cell(row, 4).value.strip() not in ("", None, False):
                                journal_id = self.env['account.journal'].sudo().search(
                                    [('name', '=', sheet.cell(row, 4).value.strip())], limit=1)
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
                            if sheet.cell(row, 5).value.strip() not in ("", None, False):
                                cd = sheet.cell(row, 5).value.strip()
                                cd = str(datetime.strptime(
                                    cd, '%Y-%m-%d').date())
                                vals.update({'date': cd})
                            else:
                                vals.update({'date': fields.Date.today()})
                            if sheet.cell(row, 6).value.strip() not in ("", None, False):
                                vals.update(
                                    {'ref': sheet.cell(row, 6).value.strip()})
                            if sheet.cell(row, 7).value not in ("", None, False):
                                vals.update(
                                    {'amount': float(sheet.cell(row, 7).value)})
                            else:
                                vals.update({'amount': 0.0})
                            if sheet.cell(row, 8).value not in ("", None, False):
                                currency_id = self.env['res.currency'].sudo().search(
                                    [('name', '=', sheet.cell(row, 8).value)], limit=1)
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
                                field_value = sheet.cell(
                                    row, k_row_index).value
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
                                counter)] = " - Value is not valid " + ustr(e)
                            counter = counter + 1
                            continue
                    if created_payment_list_for_confirm and self.is_confirm_payment:
                        payments = account_payment_obj.search(
                            [('id', 'in', created_payment_list_for_confirm)])
                        if payments:
                            for payment in payments:
                                payment.action_post()
                    else:
                        created_payment_list_for_confirm = []
                except Exception:
                    raise UserError(
                        _("Sorry, Your csv file does not match with our format"))

                if counter > 1:
                    completed_records = len(created_payment_list)
                    confirm_rec = len(created_payment_list_for_confirm)
                    res = self.show_success_msg(
                        completed_records, confirm_rec, skipped_line_no)
                    return res

