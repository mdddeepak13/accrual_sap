import cds from '@sap/cds';

const _cds = cds as any;

cds.on('served', async () => {
  cds.log('init').info('=== running cds.deploy on startup ===');
  try {
    await _cds.deploy(cds.model).to(cds.db);
    cds.log('init').info('=== cds.deploy completed ===');
  } catch (err: any) {
    cds.log('init').error('cds.deploy failed:', err?.message || err);
  }
});

export default cds.server;
