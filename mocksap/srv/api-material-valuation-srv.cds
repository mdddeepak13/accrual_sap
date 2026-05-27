using sap.s4.batch from '../db/schema';

@path: '/s4hanacloud/sap/opu/odata/sap/API_MATERIAL_VALUATION_SRV'
service API_MATERIAL_VALUATION_SRV {
  entity MaterialValuation as projection on batch.MaterialValuation;
}
