import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Ledger from "./pages/Ledger";
import Record from "./pages/Record";
import Insights from "./pages/Insights";
import Profile from "./pages/Profile";

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="ledger" element={<Ledger />} />
          <Route path="record" element={<Record />} />
          <Route path="insights" element={<Insights />} />
          <Route path="profile" element={<Profile />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
