using sap.s4.batch from '../db/schema';

@path: '/s4hanacloud/sap/opu/odata/sap/API_COSTCENTER_SRV'
service API_COSTCENTER_SRV {
  entity A_CostCenter as projection on batch.A_CostCenter;
}
