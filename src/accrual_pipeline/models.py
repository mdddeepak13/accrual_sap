"""Pydantic models for pipeline data flow.

FI / MM / CO fetcher outputs mirror SAP A2X OData field names (PascalCase)
so payloads stay debuggable against api.sap.com. `extra="ignore"` lets
us skip the dozens of fields we don't use without hand-modeling them.

The merged AccrualObject — the shape Claude sees — uses `extra="forbid"`
because we own that contract.

SAP OData v2 encodes dates as "/Date(1712707200000)/". A BeforeValidator
transparently coerces that format to a Python date; ISO strings pass
through untouched so fixtures stay readable.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict


_ODATA_DATE_RE = re.compile(r"^/Date\((-?\d+)")


def _coerce_odata_date(value: Any) -> Any:
    """Convert SAP `/Date(ms)/` to a date; pass ISO strings / dates through."""
    if isinstance(value, str):
        match = _ODATA_DATE_RE.match(value)
        if match:
            ms = int(match.group(1))
            return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date()
    return value


ODataDate = Annotated[date, BeforeValidator(_coerce_odata_date)]


class _SAPRecord(BaseModel):
    """Base for raw SAP OData records — tolerant of unmodeled fields."""

    model_config = ConfigDict(extra="ignore")


class FIJournalEntry(_SAPRecord):
    """Accrual-bearing journal entry item from ACDOCA.

    Source: Operational Journal Entry Item (A2X) API, entity
    A_OperationalAcctgDocItemCube. Field names match the cube verbatim.
    Field selection is informed by a live sandbox probe — e.g., PO linkage
    uses ``PurchasingDocument``, not ``PurchaseOrder``.
    """

    # --- Composite key ---
    CompanyCode: str
    FiscalYear: str
    AccountingDocument: str
    AccountingDocumentItem: str
    Ledger: str | None = None  # often blank on the cube; non-null only on ledger-specific postings

    # --- Posting metadata ---
    PostingDate: ODataDate | None = None
    DocumentDate: ODataDate | None = None
    AccountingDocumentType: str
    AccountingDocumentTypeName: str | None = None
    AccountingDocumentHeaderText: str | None = None
    DocumentItemText: str | None = None
    DocumentReferenceID: str | None = None
    ReferenceDocumentType: str | None = None
    FiscalPeriod: str | None = None
    IsReversal: bool = False
    IsReversed: bool = False

    # --- Amount ---
    GLAccount: str
    GLAccountName: str | None = None
    AmountInTransactionCurrency: Decimal
    TransactionCurrency: str
    AmountInCompanyCodeCurrency: Decimal | None = None
    CompanyCodeCurrency: str | None = None
    AmountInGlobalCurrency: Decimal | None = None
    GlobalCurrency: str | None = None
    DebitCreditCode: str  # "S" debit / "H" credit

    # --- PO linkage (SAP's own field names on this entity) ---
    PurchasingDocument: str | None = None
    PurchasingDocumentItem: str | None = None
    Material: str | None = None
    Supplier: str | None = None
    SupplierName: str | None = None

    # --- Invoice / GR linkage, used for accrual reconciliation ---
    InvoiceReference: str | None = None
    InvoiceReferenceFiscalYear: str | None = None
    InvoiceReceiptDate: ODataDate | None = None

    # --- CO assignment ---
    CostCenter: str | None = None
    CostCenterName: str | None = None
    ProfitCenter: str | None = None

    # --- Payroll-PECI custom fields ---
    # Populated only on FI lines that came from a Workday PECI delivery
    # (AccountingDocumentType="PY"). Null on regular FI accrual lines.
    WorkerReference: str | None = None
    PayGroupReference: str | None = None
    PayPeriodStartDate: ODataDate | None = None
    PayPeriodEndDate: ODataDate | None = None

    @property
    def accrual_id(self) -> str:
        """Composite key used as the primary identifier in AccrualObject."""
        return (
            f"{self.CompanyCode}/{self.FiscalYear}/"
            f"{self.AccountingDocument}/{self.AccountingDocumentItem}"
        )


class MMPurchaseOrder(_SAPRecord):
    """Purchase order line item with header + SES context.

    Source: Purchase Order API (A_PurchaseOrderItem). Line-level is what
    accrual reconciliation needs — SES / invoice data hang off the item.
    """

    PurchaseOrder: str
    PurchaseOrderItem: str
    PurchaseOrderType: str | None = None
    PurchasingDocumentDate: ODataDate | None = None
    Supplier: str
    SupplierName: str | None = None
    Material: str | None = None
    PurchaseOrderItemText: str | None = None
    OrderQuantity: Decimal
    OrderPriceUnit: str | None = None
    NetPriceAmount: Decimal
    DocumentCurrency: str
    AccountAssignmentCategory: str | None = None
    CostCenter: str | None = None
    GLAccount: str | None = None
    LatestGoodsReceiptDate: ODataDate | None = None
    InvoicedQuantity: Decimal | None = None
    IsFullyDelivered: bool = False
    IsFullyInvoiced: bool = False


class COCostCenter(_SAPRecord):
    """Cost center master record.

    Source: Cost Center API (API_COSTCENTER_SRV / A_CostCenter).
    """

    ControllingArea: str
    CostCenter: str
    ValidityStartDate: ODataDate
    ValidityEndDate: ODataDate
    CostCenterName: str
    Department: str | None = None
    PersonResponsibleName: str | None = None
    CompanyCode: str | None = None
    CostCenterCategory: str | None = None
    CostCenterStandardHierArea: str | None = None


class WorkdayEarning(_SAPRecord):
    Code: str
    Hours: str | None = None
    Amount: Decimal
    GL_Account: str | None = None


class WorkdayDeduction(_SAPRecord):
    Code: str
    Amount: Decimal


class WorkdayEmployerCost(_SAPRecord):
    Code: str
    Amount: Decimal
    GL_Account: str | None = None


def _unwrap_reference(value: Any) -> Any:
    """SOAP/REST reference fields come as `{"ID": "...", "Type": "..."}`.

    Reduce them to the bare ID string before pydantic sees them so the rest
    of the model stays simple. Plain strings pass through.
    """
    if isinstance(value, dict) and "ID" in value:
        return value["ID"]
    return value


WorkdayRef = Annotated[str, BeforeValidator(_unwrap_reference)]


class WorkdayPayrollResult(_SAPRecord):
    """One finalized Pay_Result record from Workday `Get_Payroll_Results`.

    Field names mirror the WSDL element names (PascalCase with underscores)
    so a live SOAP→dict parse via xmltodict feeds the same model that mock
    fixtures use.
    """

    Worker_Reference: WorkdayRef
    Worker_Name: str
    Worker_Type: str | None = None
    Worker_Status: str | None = None  # "Active" | "Terminated"
    Pay_Group_Reference: WorkdayRef
    Pay_Period_Start_Date: date
    Pay_Period_End_Date: date
    Pay_Date: date
    Cost_Center_Reference: WorkdayRef | None = None
    Currency: str = "USD"
    Days_Worked: str | None = None
    Gross_Pay: Decimal
    Net_Pay: Decimal
    Total_Employer_Cost: Decimal | None = None
    Earnings: list[WorkdayEarning] = []
    Deductions: list[WorkdayDeduction] = []
    Employer_Costs: list[WorkdayEmployerCost] = []
    Termination_Date: date | None = None

    @property
    def payroll_id(self) -> str:
        """Identifier we use to key reconciliation rows and persisted flags."""
        return f"WD/{self.Pay_Group_Reference}/{self.Pay_Period_End_Date.isoformat()}/{self.Worker_Reference}"


class PayrollAccrualReconciliation(BaseModel):
    """One row reconciling a Workday payroll result with the matching SAP FI
    payroll lines that PECI is supposed to have delivered.

    This is the shape Claude sees in the payroll prompt — every Workday
    record produces one of these, even when the FI side has no matches
    (so a missing-in-FI mismatch is observable).
    """

    model_config = ConfigDict(extra="forbid")

    payroll_id: str
    worker_id: str
    worker_name: str
    worker_status: str | None = None
    pay_group: str
    pay_period_start: date
    pay_period_end: date
    pay_date: date
    cost_center: str | None = None
    termination_date: date | None = None
    days_worked: str | None = None

    # Workday-side totals (authoritative)
    workday_gross: Decimal
    workday_net: Decimal
    workday_total_employer_cost: Decimal | None = None
    workday_earnings_by_code: dict[str, Decimal] = {}
    workday_employer_costs_by_code: dict[str, Decimal] = {}

    # FI-side totals (what PECI actually posted)
    fi_total_earnings: Decimal = Decimal("0")
    fi_total_employer_cost: Decimal = Decimal("0")
    fi_earnings_by_gl: dict[str, Decimal] = {}
    fi_employer_cost_by_gl: dict[str, Decimal] = {}
    fi_cost_centers_seen: list[str] = []
    fi_document_count: int = 0
    fi_line_count: int = 0
    fi_document_numbers: list[str] = []


class AccrualObject(BaseModel):
    """Business-shaped accrual record — 13 fields matching the finance-team
    spec. Built by normalizer.py from FI/MM/CO with SAP's OData naming
    translated to plain business language.

    Field list matches the project requirement verbatim:
      Sl.no. (injected by UI), Company code, Posting Date, Document date,
      GL Account Number, GL Description, Vendor Number, Vendor Name,
      Short text, Long text, Accrual From period, Accrual to period,
      Amount (USD).

    Additional identifier + PO/CC context are kept for the downstream
    anomaly checks (stale-PO flag, duplicate detection) — Claude sees them,
    but the UI focuses on the 13 business fields.
    """

    model_config = ConfigDict(extra="forbid")

    # --- Identifier (not in the business spec, needed for routing/persistence) ---
    accrual_id: str  # "{company_code}/{fiscal_year}/{document}/{item}"

    # --- Business fields (the 13 the UI shows) ---
    company_code: str
    posting_date: date | None = None
    document_date: date | None = None
    gl_account_number: str
    gl_description: str | None = None
    vendor_number: str | None = None
    vendor_name: str | None = None
    short_text: str | None = None
    long_text: str | None = None
    accrual_from_period: date | None = None
    accrual_to_period: date | None = None
    amount_usd: Decimal | None = None

    # --- Context for Claude's anomaly checks (not shown as columns) ---
    fiscal_year: str
    accounting_document: str
    accounting_document_item: str
    is_reversal: bool
    is_reversed: bool
    purchase_order: str | None = None
    purchase_order_item: str | None = None
    po_supplier_name: str | None = None
    po_latest_goods_receipt_date: date | None = None
    po_is_fully_invoiced: bool | None = None
    po_purchase_order_type: str | None = None
    cost_center_id: str | None = None
    cost_center_name: str | None = None
    cost_center_responsible: str | None = None
