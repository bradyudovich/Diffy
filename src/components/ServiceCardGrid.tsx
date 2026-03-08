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
    return <p className="text-gray-500 text-sm">No companies match your filter.</p>;
  }

  const visibleCompanies = companies.slice(0, visibleCount);
  const hasMore = visibleCount < companies.length;

  return (
    <>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
            onClick={() => setVisibleCount((prev) => prev + PAGE_SIZE)}
            className="rounded-full px-6 py-2 text-sm font-medium bg-white border border-gray-300 text-gray-700 hover:bg-indigo-50 hover:border-indigo-400 transition-colors shadow-sm"
          >
            Load more ({companies.length - visibleCount} remaining)
          </button>
        </div>
      )}
    </>
  );
}
