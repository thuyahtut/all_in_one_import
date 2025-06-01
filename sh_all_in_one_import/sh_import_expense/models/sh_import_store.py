# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from email.policy import default
from odoo import fields, models, _
from odoo.exceptions import UserError
import csv
import base64
from odoo.tools import ustr

class ImportStore(models.Model):
    _inherit = "sh.import.store"

    def check_sh_import_expense(self):
        value = False
        record = self.env['sh.import.base'].browse(
            self.env.context.get('active_id'))
        if record.sh_technical_name == 'sh_import_expense':
            value = True
        return value

    sh_import_expense_type = fields.Selection(related='base_id.sh_import_expense_type',readonly=False, string="Import File Type")
    sh_expense_type = fields.Selection(related='base_id.sh_expense_type', string="Import",readonly=False)
    sh_employee_type = fields.Selection(related='base_id.sh_employee_type',readonly=False, string="Employee By")
    sh_import_expense_product_type = fields.Selection(related='base_id.sh_import_expense_product_type', string="Product By", readonly=False)
    sh_import_expense_boolean = fields.Boolean(
        "Import Expense Boolean", default=check_sh_import_expense)

    def perform_the_action(self, record):
        res = super(ImportStore, self).perform_the_action(record)
        if record.base_id.sh_technical_name == 'sh_import_expense':
            self.import_expense(record)
        return res

    def import_expense(self,record):
        self = record
        # # perform import Internal transfer
        if self and self.sh_file:

            if self.sh_import_expense_type == 'csv' or self.sh_import_expense_type == 'excel':
                counter = 1
                skipped_line_no = {}
                count=0
                running_exp = None
                created_exp = False
                try:
                    if self.sh_import_expense_type == 'csv':
                        sh_file = str(base64.decodebytes(
                            self.sh_file).decode('utf-8'))
                        length_r = csv.reader(sh_file.splitlines())
                        length_reader = len(list(length_r))
                        myreader = csv.reader(sh_file.splitlines())
                        myreader = list(myreader)                       
                    elif self.sh_import_expense_type == 'excel':
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
                            if self.sh_expense_type == 'expense':
                                if row[0] != '':
                                    vals = {
                                        'name': row[0],
                                        'unit_amount': row[2],
                                        'quantity': row[3],
                                        'reference': row[4],
                                        'date': row[5] if row[5] else False,
                                        'description': row[10]
                                    }
                                    if row[1] != '':
                                        domain = []
                                        if self.sh_import_expense_product_type == 'name':
                                            domain.append(('name', '=', row[1]))
                                        elif self.sh_import_expense_product_type == 'internal_ref':
                                            domain.append(
                                                ('default_code', '=', row[1]))
                                        elif self.sh_import_expense_product_type == 'barcode':
                                            domain.append(('barcode', '=', row[1]))
                                        search_product = self.env['product.product'].search(
                                            domain, limit=1)
                                        if search_product:
                                            vals.update(
                                                {'product_id': search_product.id})
                                            if search_product.uom_id:
                                                vals.update({
                                                    'product_uom_id': search_product.uom_id.id
                                                })
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Product not found. "
                                            counter = counter + 1
                                            continue

                                    if row[6] != '':
                                        search_account = self.env["account.account"].search(
                                            [('code', '=', row[6]),('company_id','=',self.company_id.id)], limit=1)
                                        if search_account:
                                            vals.update(
                                                {'account_id': search_account.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Account not found. "
                                            counter = counter + 1
                                            continue

                                    if row[7] != '':
                                        domain = []
                                        if self.sh_employee_type == 'name':
                                            domain.append(('name', '=', row[7]))
                                        elif self.sh_employee_type == 'work_phone':
                                            domain.append(
                                                ('work_phone', '=', row[7]))
                                        elif self.sh_employee_type == 'work_email':
                                            domain.append(
                                                ('work_email', '=', row[7]))
                                        elif self.sh_employee_type == 'badge_id':
                                            domain.append(
                                                ('barcode', '=', "% s" %
                                                row[7]))
                                        search_employee = self.env["hr.employee"].sudo().search(
                                            domain, limit=1)
                                        if search_employee:
                                            vals.update(
                                                {'employee_id': search_employee.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Employee not found. "
                                            counter = counter + 1
                                            continue

                                    if row[8] != '':
                                        search_cuurency = self.env["res.currency"].search(
                                            [('name', '=', row[8])], limit=1)
                                        if search_cuurency:
                                            vals.update(
                                                {'currency_id': search_cuurency.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Currency not found. "
                                            counter = counter + 1
                                            continue

                                    if row[9] != '':
                                        if row[9] == 'Employee' or row[9] == 'employee':
                                            vals['payment_mode'] = 'own_account'
                                        elif row[9] == 'company' or row[9] == 'Company':
                                            vals['payment_mode'] = 'company_account'
                                    create_exp = self.env['hr.expense'].create(
                                        vals)
                                    if create_exp:
                                        counter += 1
                                else:
                                    skipped_line_no[str(
                                        counter)] = " - Description is empty. "
                                    counter = counter + 1
                            elif self.sh_expense_type == 'expense_sheet':
                                if row[0] != running_exp:
                                    running_exp = row[0]
                                    vals = {
                                        'name': row[1]
                                    }
                                    if row[2] != '':
                                        domain = []
                                        if self.sh_employee_type == 'name':
                                            domain.append(('name', '=', row[2]))
                                        elif self.sh_employee_type == 'work_phone':
                                            domain.append(
                                                ('work_phone', '=', row[2]))
                                        elif self.sh_employee_type == 'work_email':
                                            domain.append(
                                                ('work_email', '=', row[2]))
                                        else:
                                            domain.append(
                                                ('barcode', '=', "% s" %
                                                row[2]))
                                        search_employee = self.env["hr.employee"].search(
                                            domain, limit=1)
                                        if search_employee:
                                            vals.update(
                                                {'employee_id': search_employee.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Employee not found. "
                                            counter = counter + 1
                                            continue
                                    if row[3] != '':
                                        search_manager = self.env["res.users"].search(
                                            [('name', '=', row[3])], limit=1)
                                        if search_manager:
                                            vals.update(
                                                {'user_id': search_manager.id})
                                        else:
                                            skipped_line_no[str(
                                                counter)] = " - Manager not found. "
                                            counter = counter + 1
                                            continue
                                    created_exp = self.env['hr.expense.sheet'].create(
                                        vals)
                                if created_exp:
                                    if row[4] != '':
                                        exp_vals = {
                                            'name': row[4],
                                            'unit_amount': row[6],
                                            'quantity': row[7],
                                            'reference': row[8],
                                            'date': row[9] if row[9] else False,
                                            'description': row[13],
                                            'employee_id': created_exp.employee_id.id,
                                            'sheet_id': created_exp.id
                                        }
                                        if row[5] != '':
                                            domain = []
                                            if self.sh_import_expense_product_type == 'name':
                                                domain.append(
                                                    ('name', '=', row[5]))
                                            elif self.sh_import_expense_product_type == 'internal_ref':
                                                domain.append(
                                                    ('default_code', '=', row[5]))
                                            elif self.sh_import_expense_product_type == 'barcode':
                                                domain.append(
                                                    ('barcode', '=', row[5]))
                                            search_product = self.env['product.product'].search(
                                                domain, limit=1)
                                            if search_product:
                                                exp_vals.update(
                                                    {'product_id': search_product.id})
                                                if search_product.uom_id:
                                                    exp_vals.update({
                                                        'product_uom_id': search_product.uom_id.id
                                                    })
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Product not found. "
                                                counter = counter + 1
                                                continue

                                        if row[10] != '':
                                            search_account = self.env["account.account"].search(
                                                [('code', '=', row[10]),('company_id','=',self.company_id.id)], limit=1)
                                            if search_account:
                                                exp_vals.update(
                                                    {'account_id': search_account.id})
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Account not found. "
                                                counter = counter + 1
                                                continue
                                        if row[11] != '':
                                            search_cuurency = self.env["res.currency"].search(
                                                [('name', '=', row[11])], limit=1)
                                            if search_cuurency:
                                                exp_vals.update(
                                                    {'currency_id': search_cuurency.id})
                                            else:
                                                skipped_line_no[str(
                                                    counter)] = " - Currency not found. "
                                                counter = counter + 1
                                                continue

                                        if row[12] != '':
                                            if row[12] == 'Employee' or row[12] == 'employee':
                                                exp_vals['payment_mode'] = 'own_account'
                                            elif row[12] == 'company' or row[12] == 'Company':
                                                exp_vals['payment_mode'] = 'company_account'

                                        create_exp = self.env['hr.expense'].create(
                                            exp_vals)
                                        if create_exp:
                                            counter += 1
                                    else:
                                        skipped_line_no[str(
                                            counter)] = " - Description is empty. "
                                        counter = counter + 1
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
