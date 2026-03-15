/**
 * DashboardStats.tsx – Summary statistics banner for the landing dashboard.
 *
 * Renders four stat cards (companies tracked, industry avg score, companies
 * flagged, TOS changes logged) in a responsive grid.  Each card includes a
 * decorative icon, large value text, and a descriptive label.  All numbers are
 * wrapped in <strong> with aria-label so screen readers announce them clearly.
 */

export interface GlobalStats {
  total: number;
  industryAvg: number;
  flagged: number;
  totalChanges: number;
}

interface StatCardProps {
  icon: string;
  value: number | string;
  label: string;
  /** Tailwind colour class for the value text (defaults to white). */
  valueColor?: string;
  ariaLabel: string;
}

function StatCard({ icon, value, label, valueColor = "text-white", ariaLabel }: StatCardProps) {
  return (
    <div
      className="rounded-xl bg-white/10 border border-white/15 px-4 py-3 flex items-center gap-3
                 hover:bg-white/15 transition-colors duration-200"
      role="group"
      aria-label={ariaLabel}
    >
      <span className="text-2xl" aria-hidden="true">{icon}</span>
      <div>
        <strong className={`block text-2xl font-black leading-none ${valueColor}`}>{value}</strong>
        <span className="block text-indigo-300 text-xs mt-0.5 leading-snug">{label}</span>
      </div>
    </div>
  );
}

interface Props {
  stats: GlobalStats;
}

export default function DashboardStats({ stats }: Props) {
  return (
    <div
      className="mt-5 grid grid-cols-2 sm:grid-cols-4 gap-3 animate-slide-up"
      aria-label="Dashboard summary statistics"
    >
      <StatCard
        icon="🏢"
        value={stats.total}
        label="Companies tracked"
        ariaLabel={`${stats.total} companies tracked`}
      />
      <StatCard
        icon="📊"
        value={stats.industryAvg}
        label="Industry avg score"
        ariaLabel={`Industry average score: ${stats.industryAvg} out of 100`}
      />
      <StatCard
        icon="🚩"
        value={stats.flagged}
        label="Companies flagged"
        valueColor="text-rose-300"
        ariaLabel={`${stats.flagged} companies flagged for low scores`}
      />
      <StatCard
        icon="🔄"
        value={stats.totalChanges}
        label="TOS changes logged"
        ariaLabel={`${stats.totalChanges} terms-of-service changes logged`}
      />
    </div>
  );
}
