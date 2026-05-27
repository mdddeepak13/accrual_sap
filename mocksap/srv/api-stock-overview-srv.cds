using sap.s4.batch from '../db/schema';

@path: '/s4hanacloud/sap/opu/odata/sap/API_STOCK_OVERVIEW_SRV'
service API_STOCK_OVERVIEW_SRV {
  entity StockOverview as projection on batch.StockOverview;
}
