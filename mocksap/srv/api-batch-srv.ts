import cds from '@sap/cds';

export default cds.service.impl(function () {
  this.before(['CREATE', 'UPDATE', 'DELETE'], 'Batch', () => {
    throw new Error('Read-only mock SAP service');
  });
});
