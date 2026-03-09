/**
 * GlossaryData.ts – Plain-English translations for all terms tracked in
 * watchlist.json.  Re-exports the canonical glossary from LegalGlossary.ts
 * so that consumers can import from either module.
 */

export { LEGAL_GLOSSARY as GLOSSARY_DATA, getGlossaryDefinition } from "./LegalGlossary";
