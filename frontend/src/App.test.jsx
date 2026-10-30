import React from 'react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import App from './App.jsx';
const incoming={messageId:'m-1',sender:'guest@example.com',channel:'EMAIL',timestamp:'2026-10-30T12:00:00Z',body:'Please reimburse my meal expense.'};
const base={caseId:'case-clear',subject:'Meal expense',status:'NEW',owner:{type:'AI',id:'demo-ai'},queue:'Service',priority:'Normal',nextAction:'Assess',version:1,snapshot:{messages:[incoming],attachments:[],knownFacts:[],missingInformation:[]},sourceReferences:[{sourceId:'demo-policy',version:'1'}],runResults:[],history:[]};
let current,requests,failProcess;
beforeEach(()=>{
 current=structuredClone(base);requests=[];failProcess=false;
 vi.stubGlobal('ResizeObserver',class{observe(){} disconnect(){}});
 vi.stubGlobal('fetch',vi.fn(async(url,options)=>{
   const form=options?.body instanceof FormData ? options.body : null;const body=form ? JSON.parse(form.get('metadata')) : options?.body&&JSON.parse(options.body);requests.push({url,body,form});let result;
   if(url.endsWith('/process')) {
     if(failProcess){failProcess=false;return {ok:false,status:503,json:async()=>({error:{message:'Temporarily unavailable',code:'STORAGE_UNAVAILABLE'}})};}
     current={...current,status:'RESOLVED',version:current.version+1,snapshot:{...current.snapshot,messages:[...current.snapshot.messages,{...incoming,messageId:'out-1',sender:'condor-service@example.com',body:'Simulated reimbursement approved.'}]}};result={case:current,runResult:{status:'SUCCEEDED'}};
   } else if(url==='/api/inbound/messages'){
     current={...current,version:current.version+1,status:'IN_PROGRESS',snapshot:{...current.snapshot,messages:[...current.snapshot.messages,{...incoming,messageId:body.messageId,body:body.body}]}};result={messageId:body.messageId,caseId:current.caseId,caseVersion:current.version,customerCaseUrl:'/portal/cases/'+current.caseId};
   } else if(url==='/api/cases')result=[current];
   else if(url.startsWith('/api/events'))result={events:[{eventId:'evt-1',sequence:1,stepId:'intake',summary:'Intake recorded'}],cursor:1};
   else result=current;
   return {ok:true,json:async()=>result};
 }));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
test('canonical System 1 case renders and one processing command updates dashboard',async()=>{
 render(<App/>);await screen.findByText('Please reimburse my meal expense.');fireEvent.click(screen.getByRole('button',{name:'Start AI processing'}));
 await screen.findByText('Simulated reimbursement approved.');const commands=requests.filter(r=>r.url.endsWith('/process'));
 expect(commands).toHaveLength(1);expect(commands[0].body.expectedCaseVersion).toBe(1);expect(commands[0].body.requestId).toBeTruthy();
 expect(within(screen.getByRole('button',{name:/^Resolved/})).getByText('1')).toBeTruthy();
});
test('human ownership blocks AI processing and customer reply stays human-owned',async()=>{
 current={...current,owner:{type:'HUMAN',id:'demo-agent'},status:'IN_PROGRESS'};render(<App/>);await screen.findByText('Please reimburse my meal expense.');
 expect(screen.getByRole('button',{name:'Start AI processing'}).disabled).toBe(true);fireEvent.click(screen.getByRole('button',{name:'Submit reply & assess'}));
 await waitFor(()=>expect(requests.filter(r=>r.url==='/api/inbound/messages')).toHaveLength(1));expect(requests.filter(r=>r.url.endsWith('/process'))).toHaveLength(0);
});
test('console reply simulation uses same case and then latest version exactly once',async()=>{
 current={...current,status:'WAITING_FOR_CUSTOMER',version:3};render(<App/>);await screen.findByText('Please reimburse my meal expense.');
 expect(screen.queryByRole('button',{name:'Customer view'})).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Submit reply & assess'}));
 await screen.findByText('Simulated reimbursement approved.');const inbound=requests.find(r=>r.url==='/api/inbound/messages');expect(inbound.body.caseId).toBe('case-clear');expect(inbound.body.body).toBe('42.00 EUR');
 expect(requests.filter(r=>r.url.endsWith('/process'))).toHaveLength(1);expect(requests.find(r=>r.url.endsWith('/process')).body.expectedCaseVersion).toBe(4);
 expect(screen.queryByRole('button',{name:'Reset demo'})).toBeNull();expect(inbound.body.channel).toBe('PORTAL');expect(inbound.body.subject).toBe('Meal expense');
});
test('temporary processing failure retries original key without resending customer message',async()=>{
 failProcess=true;render(<App/>);await screen.findByText('Please reimburse my meal expense.');fireEvent.click(screen.getByRole('button',{name:'Submit reply & assess'}));
 fireEvent.click(await screen.findByRole('button',{name:'Retry action'}));await screen.findByText('Simulated reimbursement approved.');
 expect(requests.filter(r=>r.url==='/api/inbound/messages')).toHaveLength(1);const processes=requests.filter(r=>r.url.endsWith('/process'));expect(processes).toHaveLength(2);expect(processes[0].body).toEqual(processes[1].body);
});
test('process replay and format changes do not mutate data',async()=>{
 render(<App/>);await screen.findByText('Intake recorded');fireEvent.click(screen.getByRole('button',{name:'Process view'}));
 fireEvent.change(screen.getByLabelText('Format'),{target:{value:'4:3'}});fireEvent.click(screen.getByRole('button',{name:'Start replay',exact:true}));expect(requests.filter(r=>r.body)).toHaveLength(0);
});

test('attachment selection waits for reply and sends one atomic multipart intake',async()=>{
 render(<App/>);await screen.findByText('Please reimburse my meal expense.');
 const file=new File(['synthetic'], 'receipt.pdf', {type:'application/pdf'});
 fireEvent.change(screen.getByLabelText(/Add synthetic attachment/),{target:{files:[file]}});
 expect(screen.getByRole('status').textContent).toContain('receipt.pdf');
 expect(requests.filter(r=>r.url==='/api/inbound/messages')).toHaveLength(0);
 fireEvent.click(screen.getByRole('button',{name:'Submit reply & assess'}));
 await screen.findByText('Simulated reimbursement approved.');
 const submits=requests.filter(r=>r.url==='/api/inbound/messages');expect(submits).toHaveLength(1);
 expect(submits[0].form.get('files')).toBe(file);expect(submits[0].body.caseId).toBe('case-clear');
 expect(screen.queryByRole('status')).toBeNull();
});
