import React from 'react';
import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import CustomerView from './CustomerView.jsx';

const detail = {
  id: 'case-evidence', subject: 'Meal receipt', status: 'WAITING_FOR_CUSTOMER',
  messages: [{ messageId: 'question', direction: 'OUTBOUND', body: 'Please provide the amount and currency.' }],
  attachments: [], handoff: { summary: 'INTERNAL ONLY' }, facts: ['INTERNAL FACT'],
};
afterEach(cleanup);

test('shows the customer conversation without internal case context and keeps a failed reply draft', async () => {
  const onReply = vi.fn().mockResolvedValue(false);
  render(<CustomerView caseDetail={detail} onReply={onReply} onUpload={vi.fn()} />);
  expect(screen.getByText('Please provide the amount and currency.')).toBeTruthy();
  expect(screen.queryByText('INTERNAL ONLY')).toBeNull();
  expect(screen.queryByText('INTERNAL FACT')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Send reply' }));
  await screen.findByRole('alert');
  expect(onReply).toHaveBeenCalledWith('42.00 EUR', []);
  expect(screen.getByLabelText('Your reply').value).toBe('42.00 EUR');
});

test('waits for upload and submits the returned attachment on the same case once', async () => {
  let finishUpload;
  const onUpload = vi.fn(() => new Promise(resolve => { finishUpload = resolve; }));
  const onReply = vi.fn().mockResolvedValue(true);
  render(<CustomerView caseDetail={detail} onReply={onReply} onUpload={onUpload} />);
  fireEvent.click(screen.getByRole('button', { name: 'Add demo receipt · EUR 42.00' }));
  expect(onUpload).toHaveBeenCalledOnce();
  expect(screen.getByRole('button', { name: 'Processing …' }).disabled).toBe(true);
  finishUpload({ attachmentId: 'receipt-1' });
  await screen.findByText('1 receipt(s) saved for your reply.');
  fireEvent.click(screen.getByRole('button', { name: 'Send reply' }));
  await waitFor(() => expect(screen.getByLabelText('Your reply').value).toBe(''));
  expect(onReply).toHaveBeenCalledExactlyOnceWith('42.00 EUR', ['receipt-1']);
  expect(screen.getByText('CASE case-evidence')).toBeTruthy();
});

test('failed upload prevents submission until the customer explicitly continues or retries', async () => {
  const onReply = vi.fn();
  render(<CustomerView caseDetail={detail} onReply={onReply} onUpload={vi.fn().mockRejectedValue(new Error('Upload unavailable'))} />);
  fireEvent.click(screen.getByRole('button', { name: 'Add demo receipt · EUR 42.00' }));
  await screen.findByText('Upload unavailable');
  const send = screen.getByRole('button', { name: 'Send reply' });
  expect(send.disabled).toBe(true);
  fireEvent.click(send);
  expect(onReply).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Continue without another upload' }));
  expect(screen.getByRole('button', { name: 'Send reply' }).disabled).toBe(false);
});

test('renders persisted simulated reimbursement and case-scoped attachment link', () => {
  render(<CustomerView caseDetail={{ ...detail, status: 'RESOLVED', financialPositions: [{ amountMinor: 4200, currency: 'EUR' }], attachments: [{ attachmentId: 'receipt-1', filename: 'receipt.txt' }] }} onReply={vi.fn()} onUpload={vi.fn()} />);
  expect(screen.getByText('€42.00')).toBeTruthy();
  expect(screen.getByRole('link', { name: '↗ receipt.txt' }).getAttribute('href')).toBe('/api/cases/case-evidence/attachments/receipt-1');
  expect(screen.getByText('Resolved')).toBeTruthy();
});
