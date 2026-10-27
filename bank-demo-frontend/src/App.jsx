import { Routes, Route } from "react-router-dom";
import { SseProvider } from "./components/shared/SseProvider";
import { Shell } from "./components/shared/Shell";
import Dashboard from "./pages/Dashboard";
import Pipeline from "./pages/Pipeline";
import Loans from "./pages/Loans";
import LoanDetail from "./pages/LoanDetail";
import Bilan from "./pages/Bilan";

export default function App() {
  return (
    <SseProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/pipeline" element={<Pipeline />} />
          <Route path="/loans" element={<Loans />} />
          <Route path="/loans/:facilityId" element={<LoanDetail />} />
          <Route path="/bilan" element={<Bilan />} />
        </Route>
      </Routes>
    </SseProvider>
  );
}
