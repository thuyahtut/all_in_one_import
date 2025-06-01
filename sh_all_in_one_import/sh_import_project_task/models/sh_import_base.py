# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, _, api

class ImportBase(models.Model):
    _inherit = "sh.import.base"

    @api.model
    def default_company(self):
        return self.env.company

    project_id = fields.Many2one("project.project", string="Project")
    sh_import_task_import_type = fields.Selection([
        ('csv', 'CSV File'),
        ('excel', 'Excel File')
    ], default="csv", string="Import File Type", required=True)
    user_ids = fields.Many2many('res.users', string="Assigned to")
    import_method = fields.Selection([
        ('default', 'By Default'),
        ('proj_user_wise', 'Project and user wise import')
    ], default="default", string="Import Method", required=True)
    sh_company_id_task = fields.Many2one(
        'res.company', string='Company', default=default_company, required=True)
    sh_import_task_boolean = fields.Boolean(
        "Import Task Boolean", compute="check_sh_import_task")

    def check_sh_import_task(self):
        if self.sh_technical_name == 'sh_import_project_task':
            self.sh_import_task_boolean = True
        else:
            self.sh_import_task_boolean = False

    def import_task_apply(self):
        self.write({
            'project_id': self.project_id.id,
            'sh_import_task_import_type': self.sh_import_task_import_type,
            'user_ids': [(6,0,self.user_ids.ids or [])],
            'import_method':self.import_method,
            'on_error': self.on_error,
            'import_limit': self.import_limit
        })
