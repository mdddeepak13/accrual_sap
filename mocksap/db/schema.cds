namespace sap.s4.batch;

entity Batch {
  key Batch                       : String(10);
      Material                    : String(40);
      MaterialDescription         : String(60);
      TherapeuticCategory         : String(20);
      BatchIdentifyingPlant       : String(4);
      PlantName                   : String(40);
      ShelfLifeExpirationDate     : Date;
      ManufactureDate             : Date;
      LastGoodsReceiptDate        : Date;
      BatchIsMarkedForDeletion    : Boolean default false;
      MatlBatchIsInRstrcdUseStock : Boolean default false;
      Supplier                    : String(10);
      SupplierName                : String(40);
      CountryOfOrigin             : String(3);
      Quantity                    : Decimal(15, 3);
      BaseUnit                    : String(3);
}

// MB52 — Display Warehouse Stocks of Material (per material × plant × stor loc × batch).
entity StockOverview {
  key Material               : String(40);
  key Plant                  : String(4);
  key StorageLocation        : String(4);
  key Batch                  : String(10);
      UnrestrictedStock      : Decimal(15, 3);
      QualityInspectionStock : Decimal(15, 3);
      BlockedStock           : Decimal(15, 3);
      RestrictedStock        : Decimal(15, 3);
      BaseUnit               : String(3);
      LastGoodsReceiptDate   : Date;
      ShelfLifeExpiration    : Date;
      Supplier               : String(10);
      CountryOfOrigin        : String(3);
      DistressReason         : String(30);
      WritedownPercent       : Decimal(5, 2);
      WritedownAmount        : Decimal(15, 2);
}

// MBEW — Material Valuation (per material × valuation area).
entity MaterialValuation {
  key Material        : String(40);
  key ValuationArea   : String(4);
      ValuationClass  : String(4);
      Currency        : String(3);
      StandardPrice   : Decimal(13, 2);
      PriceUnit       : Decimal(5, 0);
      MovingAvgPrice  : Decimal(13, 2);
      TotalStockQty   : Decimal(15, 3);
      TotalStockValue : Decimal(15, 2);
}

// API_PURCHASEORDER_PROCESS_SRV — Purchase order items.
entity A_PurchaseOrderItem {
  key PurchaseOrder             : String(10);
  key PurchaseOrderItem         : String(6);
      PurchaseOrderType         : String(4);
      PurchasingDocumentDate    : Date;
      Supplier                  : String(10);
      SupplierName              : String(80);
      Material                  : String(40);
      PurchaseOrderItemText     : String(80);
      OrderQuantity             : Decimal(15, 3);
      OrderPriceUnit            : String(3);
      NetPriceAmount            : Decimal(15, 2);
      DocumentCurrency          : String(3);
      AccountAssignmentCategory : String(2);
      CostCenter                : String(10);
      GLAccount                 : String(10);
      LatestGoodsReceiptDate    : Date;
      InvoicedQuantity          : Decimal(15, 3);
      IsFullyDelivered          : Boolean default false;
      IsFullyInvoiced           : Boolean default false;
}

// API_COSTCENTERPLAN_SRV — Cost-center plan rows by year × period × account.
entity A_CostCenterPlan {
  key CompanyCode                    : String(4);
  key FiscalYear                     : String(4);
  key FiscalPeriod                   : String(3);
  key CostCenter                     : String(10);
  key GLAccount                      : String(10);
      CostCenterName                 : String(50);
      GLAccountName                  : String(80);
      PlannedAmountInGlobalCurrency  : Decimal(15, 2);
      Currency                       : String(3);
}

// API_COSTCENTER_SRV — Controlling cost-center master.
entity A_CostCenter {
  key ControllingArea            : String(4);
  key CostCenter                 : String(10);
  key ValidityEndDate            : Date;
      ValidityStartDate          : Date;
      CostCenterName             : String(50);
      Department                 : String(50);
      PersonResponsibleName      : String(80);
      CompanyCode                : String(4);
      CostCenterCategory         : String(2);
      CostCenterStandardHierArea : String(20);
}

// API_OPLACCTGDOCITEMCUBE_SRV — Operational Accounting Document Item Cube.
// Powers the "current accruals" view.
entity A_OperationalAcctgDocItemCube {
  key CompanyCode                  : String(4);
  key FiscalYear                   : String(4);
  key AccountingDocument           : String(10);
  key AccountingDocumentItem       : String(6);
      FiscalPeriod                 : String(3);
      Ledger                       : String(2);
      PostingDate                  : Date;
      DocumentDate                 : Date;
      AccountingDocumentType       : String(2);
      AccountingDocumentTypeName   : String(50);
      AccountingDocumentHeaderText : String(80);
      DocumentItemText             : String(80);
      DocumentReferenceID          : String(20);
      ReferenceDocumentType        : String(10);
      IsReversal                   : Boolean default false;
      IsReversed                   : Boolean default false;
      GLAccount                    : String(10);
      GLAccountName                : String(80);
      AmountInTransactionCurrency  : Decimal(15, 2);
      TransactionCurrency          : String(3);
      AmountInCompanyCodeCurrency  : Decimal(15, 2);
      CompanyCodeCurrency          : String(3);
      AmountInGlobalCurrency       : Decimal(15, 2);
      GlobalCurrency               : String(3);
      DebitCreditCode              : String(1);
      PurchasingDocument           : String(10);
      PurchasingDocumentItem       : String(6);
      Material                     : String(40);
      Supplier                     : String(10);
      SupplierName                 : String(80);
      InvoiceReference             : String(20);
      InvoiceReferenceFiscalYear   : String(4);
      InvoiceReceiptDate           : Date;
      CostCenter                   : String(10);
      CostCenterName               : String(50);
      ProfitCenter                 : String(10);
}
