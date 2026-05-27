using sap.s4.batch from '../db/schema';

@path: '/s4hanacloud/sap/opu/odata/sap/API_COSTCENTERPLAN_SRV'
service API_COSTCENTERPLAN_SRV {
  entity A_CostCenterPlan as projection on batch.A_CostCenterPlan;
}
