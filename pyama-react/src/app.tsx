import { HashRouter, Routes, Route } from "react-router-dom";
import { Navbar } from "./components/layout/navbar";
import {
  ProcessingPage,
  VisualizationPage,
  AnalysisPage,
  ChatPage,
  DashboardPage,
} from "./pages";

export function App() {
  return (
    <HashRouter>
      <div className="h-screen flex flex-col bg-background overflow-hidden">
        <Navbar />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<ProcessingPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/visualization" element={<VisualizationPage />} />
            <Route path="/analysis" element={<AnalysisPage />} />
            <Route path="/chat" element={<ChatPage />} />
          </Routes>
        </main>
      </div>
    </HashRouter>
  );
}
