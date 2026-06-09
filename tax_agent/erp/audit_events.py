"""Audit action constants for ERP import pipeline。

避免 audit_log 里的 action 字符串漂移。
"""

ERP_IMPORT_STARTED = "erp.import.started"
ERP_IMPORT_PARSED = "erp.import.parsed"
ERP_IMPORT_REJECTED_ROW = "erp.import.rejected_row"
ERP_IMPORT_FAILED = "erp.import.failed"
ERP_RECONCILE_COMPUTED = "erp.reconcile.computed"
ERP_COMPUTE_MODE_OVERRIDDEN = "erp.compute_mode.overridden"
