import Link from 'next/link';
import GlassContainer from '../components/GlassContainer';

export default function Landing() {
  return (
    <div className="flex flex-col items-center justify-center py-20 px-6 space-y-12">
      <div className="text-center space-y-4 max-w-2xl">
        <h1 className="text-5xl md:text-6xl neon-text">Interchained Node Operator Portal</h1>
        <p className="text-lg text-slate-300">
          Track node uptime, monitor performance, and earn daily rewards for
          keeping the Interchained network resilient. Login to access your
          personal dashboard.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/login"
            className="px-6 py-3 rounded-full bg-gradient-to-r from-neon-pink to-neon-blue font-heading uppercase tracking-widest"
          >
            Enter Portal
          </Link>
          <Link
            href="/rewards"
            className="px-6 py-3 rounded-full border border-slate-600/60 hover:border-neon-blue transition"
          >
            View Rewards
          </Link>
        </div>
      </div>
      <GlassContainer>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-left">
          {[
            {
              title: 'Real-time Monitoring',
              description:
                'Background health checks run every 60 seconds to record availability, latency, and chain height.',
            },
            {
              title: 'Performance Weighted Rewards',
              description:
                'Daily payouts are automatically shared among active operators based on uptime score.',
            },
            {
              title: 'Neon Control Center',
              description:
                'A glassmorphic UI with animated charts and badges keeps node ops futuristic and fun.',
            },
          ].map((card) => (
            <div key={card.title} className="space-y-2">
              <h3 className="text-xl font-heading text-neon-blue">{card.title}</h3>
              <p className="text-slate-300 text-sm">{card.description}</p>
            </div>
          ))}
        </div>
      </GlassContainer>
    </div>
  );
}
