"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const cds_1 = __importDefault(require("@sap/cds"));
const _cds = cds_1.default;
cds_1.default.on('served', async () => {
    cds_1.default.log('init').info('=== running cds.deploy on startup ===');
    try {
        await _cds.deploy(cds_1.default.model).to(cds_1.default.db);
        cds_1.default.log('init').info('=== cds.deploy completed ===');
    }
    catch (err) {
        cds_1.default.log('init').error('cds.deploy failed:', err?.message || err);
    }
});
exports.default = cds_1.default.server;
//# sourceMappingURL=server.js.map