import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Reader } from "@/routes/Reader";
import { Limitations } from "@/routes/Limitations";
import { Search } from "@/routes/Search";
import { useParams } from "react-router-dom";

/** `/hadith/42` was al-Tajrid before there was anything else. */
function LegacyRecordRedirect() {
  const { number } = useParams();
  return <Navigate to={`/tajrid/read/${number ?? 1}`} replace />;
}

/**
 * Phase 5 shell. `/` opens at the first hadith; every record is addressed by
 * its display number. An unknown number is handled inside Reader rather than
 * by a catch-all, so the header and jump-to control stay usable — a dead end
 * with no way out is worse than a wrong page.
 */
export default function App() {
  return (
    // GitHub Pages project sites serve from /<repo>/, so the router must be
    // told where the app starts. Vite's `base` rewrites asset and data URLs but
    // NOT route matching: without this, /Guided-Reader/hadith/1 is compared
    // against the route "/hadith/:number", fails, falls through to the
    // catch-all, and every page renders the "no such hadith" state.
    // BASE_URL is "/" for a root deploy, so this is a no-op there.
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <Routes>
        <Route path="/" element={<Navigate to="/tajrid/read/1" replace />} />

        {/* Corpus-scoped routes. The book lives in the URL, so a link carries
            which text it points at and a switch is a navigation rather than
            hidden state. */}
        <Route path="/:corpus/read/:number" element={<Reader />} />
        <Route path="/:corpus/search" element={<Search />} />

        {/* Every link handed out so far has the old shape. Breaking them is
            not acceptable and a redirect is three lines. */}
        <Route path="/hadith/:number" element={<LegacyRecordRedirect />} />
        <Route path="/search" element={<Navigate to="/tajrid/search" replace />} />

        <Route path="/about" element={<Limitations />} />
        <Route path="*" element={<Reader />} />
      </Routes>
    </BrowserRouter>
  );
}
