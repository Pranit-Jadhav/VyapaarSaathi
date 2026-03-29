import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useStore } from "./store/useStore";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Ledger from "./pages/Ledger";
import Record from "./pages/Record";
import Insights from "./pages/Insights";
import Profile from "./pages/Profile";
import Onboarding from "./pages/Onboarding";
import Inventory from "./pages/Inventory";

export default function App() {
  const { hasOnboarded } = useStore();

  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <Routes>
        {/* Onboarding Route */}
        <Route 
          path="/onboarding" 
          element={hasOnboarded ? <Navigate to="/" replace /> : <Onboarding />} 
        />
        
        {/* Main Dashboard Layout */}
        <Route 
          path="/" 
          element={hasOnboarded ? <Layout /> : <Navigate to="/onboarding" replace />}
        >
          <Route index element={<Home />} />
          <Route path="ledger" element={<Ledger />} />
          <Route path="record" element={<Record />} />
          <Route path="insights" element={<Insights />} />
          <Route path="inventory" element={<Inventory />} />
          <Route path="profile" element={<Profile />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
