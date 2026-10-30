import { expect, test } from 'vitest';
import { caseForView } from './api.js';
test('financial display uses deduplicated accepted actions rather than AI proposals',()=>{
 const position={type:'REIMBURSEMENT',amountMinor:4200,currency:'EUR'};
 const value={caseId:'case-1',version:2,status:'RESOLVED',snapshot:{messages:[]},runResults:[{proposedAction:{type:'RESOLVE',payload:{financialPositions:[position]}}}],history:[]};
 expect(caseForView(value).financialPositions).toEqual([]);
 value.history=[{type:'action.applied',data:{actionId:'action-1',financialPositions:[position]}},{type:'action.applied',data:{actionId:'action-1',financialPositions:[position]}}];
 expect(caseForView(value).financialPositions).toEqual([position]);
});
