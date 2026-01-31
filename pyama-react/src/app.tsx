import { HashRouter, Routes, Route } from "react-router-dom";
import { Navbar } from "./components/layout/navbar";
import {
  ProcessingPage,
  VisualizationPage,
  AnalysisPage,
  ChatPage,
} from "./pages";
import { ChatProvider } from "./contexts";

export function App() {
  return (
    <ChatProvider>
      <HashRouter>
        <div className="h-screen flex flex-col bg-background overflow-hidden">
          <Navbar />
          <main className="flex-1 overflow-y-auto">
            <Routes>
              <Route path="/" element={<ProcessingPage />} />
              <Route path="/visualization" element={<VisualizationPage />} />
              <Route path="/analysis" element={<AnalysisPage />} />
              <Route path="/chat" element={<ChatPage />} />
            </Routes>
          </main>
        </div>
      </HashRouter>
    </ChatProvider>
  );
}
