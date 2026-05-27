using sap.s4.batch from '../db/schema';

@path: '/s4hanacloud/sap/opu/odata/sap/API_BATCH_SRV'
service API_BATCH_SRV {
  entity Batch as projection on batch.Batch;
}
