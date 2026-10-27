import { Link, Route, Routes } from "react-router-dom";
import { TopBar } from "./components/TopBar";
import { BilanPage } from "./pages/BilanPage";
import { FacilitiesPage } from "./pages/FacilitiesPage";
import { GovernancePage } from "./pages/GovernancePage";
import { PipelinePage } from "./pages/PipelinePage";
import { PrudentialPage } from "./pages/PrudentialPage";
import { BoardProvider } from "./state/board";

function NotFound() {
  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Not found</h1>
          <p>
            That address is not part of the admin. <Link to="/">Back to the origination line</Link>.
          </p>
        </div>
      </div>
    </main>
  );
}

export function App() {
  return (
    <BoardProvider>
      <TopBar />
      <Routes>
        <Route path="/" element={<PipelinePage />} />
        <Route path="/facilities" element={<FacilitiesPage />} />
        <Route path="/prudential" element={<PrudentialPage />} />
        <Route path="/bilan" element={<BilanPage />} />
        <Route path="/governance" element={<GovernancePage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BoardProvider>
  );
}
