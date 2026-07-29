import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Reader } from "@/routes/Reader";
import { Limitations } from "@/routes/Limitations";
import { Search } from "@/routes/Search";

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
        <Route path="/" element={<Navigate to="/hadith/1" replace />} />
        <Route path="/hadith/:number" element={<Reader />} />
        <Route path="/about" element={<Limitations />} />
        <Route path="/search" element={<Search />} />
        <Route path="*" element={<Reader />} />
      </Routes>
    </BrowserRouter>
  );
}
