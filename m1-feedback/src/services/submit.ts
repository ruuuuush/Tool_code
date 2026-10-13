import type { Ticket } from '../domain/ticket';

export interface DemoResult {
  mode: 'demo';
  ticket: Ticket;
}

export async function simulateSubmission(ticket: Ticket): Promise<DemoResult> {
  await new Promise<void>((resolve) => window.setTimeout(resolve, 650));
  return { mode: 'demo', ticket };
}
