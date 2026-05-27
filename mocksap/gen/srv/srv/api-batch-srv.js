"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const cds_1 = __importDefault(require("@sap/cds"));
exports.default = cds_1.default.service.impl(function () {
    this.before(['CREATE', 'UPDATE', 'DELETE'], 'Batch', () => {
        throw new Error('Read-only mock SAP service');
    });
});
//# sourceMappingURL=api-batch-srv.js.map