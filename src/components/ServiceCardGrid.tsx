import { useState } from "react";
import type { CompanyResult } from "../types";
import ServiceCard from "./ServiceCard";

interface Props {
  companies: CompanyResult[];
  onSelectCompany: (company: CompanyResult) => void;
}

const PAGE_SIZE = 12;

export default function ServiceCardGrid({ companies, onSelectCompany }: Props) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  if (companies.length === 0) {
    return (
      <p className="text-gray-500 text-sm" role="status" aria-live="polite">
        No companies match your filter.
      </p>
    );
  }

  const visibleCompanies = companies.slice(0, visibleCount);
  const hasMore = visibleCount < companies.length;
  const remaining = companies.length - visibleCount;

  return (
    <>
      <ul
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 animate-slide-up"
        aria-label={`Showing ${visibleCompanies.length} of ${companies.length} companies`}
      >
        {visibleCompanies.map((company) => (
          <ServiceCard
            key={company.name}
            company={company}
            onSelectCompany={onSelectCompany}
          />
        ))}
      </ul>
      {hasMore && (
        <div className="mt-6 flex justify-center">
          <button
            type="button"
            onClick={() => setVisibleCount((prev) => prev + PAGE_SIZE)}
            aria-label={`Load ${Math.min(PAGE_SIZE, remaining)} more companies (${remaining} remaining)`}
            className="rounded-full px-6 py-2 text-sm font-medium bg-white border border-gray-300
                       text-gray-700 hover:bg-indigo-50 hover:border-indigo-400 transition-colors
                       shadow-sm focus-visible:outline-none focus-visible:ring-2
                       focus-visible:ring-indigo-500 focus-visible:ring-offset-1"
          >
            Load more ({remaining} remaining)
          </button>
        </div>
      )}
    </>
  );
}
