using sap.s4.batch from '../db/schema';

@path: '/s4hanacloud/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV'
service API_PURCHASEORDER_PROCESS_SRV {
  entity A_PurchaseOrderItem as projection on batch.A_PurchaseOrderItem;
}
