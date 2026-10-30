import React from 'react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from './App.jsx';
const base = { id:'case-clear',subject:'Test case',status:'NEW',owner:{type:'AI'},queue:'Service',priority:'Normal',nextAction:'Assess',caseVersion:1,messages:[],facts:[],sourceReferences:[],attachments:[],runResults:[] };
let current, requests;
beforeEach(()=>{
 current=structuredClone(base);requests=[];
 vi.stubGlobal('ResizeObserver',class{observe(){} disconnect(){}});
 vi.stubGlobal('fetch',vi.fn(async(url,options)=>{
   requests.push({url,body:options?.body&&JSON.parse(options.body)});
   let result;
   if(url.endsWith('/process')) {current={...current,status:'RESOLVED',caseVersion:2,messages:[{messageId:'out-1',direction:'OUTBOUND',body:'Simulated reply'}]};result={case:current};}
   else if(url==='/api/cases')result=[current];
   else if(url.startsWith('/api/events'))result={events:[{eventId:'evt-1',sequence:1,stepId:'intake',summary:'Intake recorded'}],cursor:1};
   else result=current;
   return {ok:true,json:async()=>result};
 }));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
test('starts one processing command and displays the returned resolved state',async()=>{
 render(<App/>);
 await waitFor(()=>expect(screen.getByRole('button',{name:'▶ Start demo'}).disabled).toBe(false));
 fireEvent.click(screen.getByRole('button',{name:'▶ Start demo'}));
 await screen.findByText('Resolved');
 const commands=requests.filter(r=>r.url.endsWith('/process'));
 expect(commands).toHaveLength(1);expect(commands[0].body.expectedCaseVersion).toBe(1);expect(commands[0].body.requestId).toBeTruthy();
});
test('console shows server messages and blocks AI processing for a human owner',async()=>{
 current={...base,owner:{type:'HUMAN'},status:'IN_PROGRESS',messages:[{messageId:'m-1',direction:'INBOUND',body:'Please review personally'}]};
 render(<App/>);fireEvent.click(screen.getByRole('button',{name:'Service console',exact:true}));
 await screen.findByText('Please review personally');
 expect(screen.getByRole('button',{name:'Start AI processing'}).disabled).toBe(true);
});
test('changing presentation format and replay controls does not mutate data',async()=>{
 render(<App/>);await screen.findByText('Intake recorded');
 fireEvent.change(screen.getByLabelText('Format'),{target:{value:'4:3'}});
 fireEvent.click(screen.getByRole('button',{name:'Start replay',exact:true}));
 expect(requests.filter(r=>r.body)).toHaveLength(0);
 expect(screen.getByLabelText('Format').value).toBe('4:3');
});
