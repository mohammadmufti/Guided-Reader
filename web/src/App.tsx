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
    <BrowserRouter>
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
