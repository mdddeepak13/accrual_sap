using sap.s4.batch from '../db/schema';

@path: '/s4hanacloud/sap/opu/odata/sap/API_OPLACCTGDOCITEMCUBE_SRV'
service API_OPLACCTGDOCITEMCUBE_SRV {
  entity A_OperationalAcctgDocItemCube as projection on batch.A_OperationalAcctgDocItemCube;
}
