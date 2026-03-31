import { TelemetryEvent } from '../types';

export const AnalyticsDashboard = ({ events }: { events: TelemetryEvent[] }) => {
  const counts = events.reduce<Record<string, number>>((acc, event) => {
    acc[event.eventName] = (acc[event.eventName] ?? 0) + 1;
    return acc;
  }, {});

  const dropoff = [...events].reverse().find((e: TelemetryEvent) => e.eventName === 'wizard_abandoned')?.dropoff_question_id;

  return (
    <section className="analytics-box">
      <h3>Mock Admin Analytics View</h3>
      <p>Total events: {events.length}</p>
      <p>Potential dropoff question: {dropoff ?? 'none'}</p>
      <ul>
        {Object.entries(counts).map(([name, count]) => (
          <li key={name}>{name}: {count}</li>
        ))}
      </ul>
    </section>
  );
};
