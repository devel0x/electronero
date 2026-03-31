import { TelemetryEvent } from '../types';

const eventStore: TelemetryEvent[] = [];

export const track = (eventName: string, payload: Omit<TelemetryEvent, 'eventName'>): void => {
  const event: TelemetryEvent = { eventName, ...payload };
  eventStore.push(event);
  // eslint-disable-next-line no-console
  console.log('[telemetry]', eventName, event);
};

export const getTelemetryEvents = (): TelemetryEvent[] => [...eventStore];
