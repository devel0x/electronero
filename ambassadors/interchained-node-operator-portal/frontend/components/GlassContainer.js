export default function GlassContainer({ children, className = '' }) {
  return (
    <div className={`glass-panel p-8 transition transform hover:-translate-y-1 hover:shadow-neon ${className}`}>
      {children}
    </div>
  );
}
