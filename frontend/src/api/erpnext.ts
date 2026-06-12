/** Re-export of the ERPNext status API method (lives in client.ts). */
import { api } from './client';

export type ErpNextStatus = Awaited<ReturnType<typeof api.erp.erpnextStatus>>;

export async function getErpNextStatus(): Promise<ErpNextStatus> {
  return api.erp.erpnextStatus();
}
