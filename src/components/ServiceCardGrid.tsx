import type { CompanyResult } from "../types";
import ServiceCard from "./ServiceCard";

interface Props {
  companies: CompanyResult[];
  onSelectCompany: (company: CompanyResult) => void;
}

export default function ServiceCardGrid({ companies, onSelectCompany }: Props) {
  if (companies.length === 0) {
    return <p className="text-gray-500 text-sm">No companies match your filter.</p>;
  }

  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {companies.map((company) => (
        <ServiceCard
          key={company.name}
          company={company}
          onSelectCompany={onSelectCompany}
        />
      ))}
    </ul>
  );
}
