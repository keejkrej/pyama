import Router from 'preact-router';
import { Navbar } from './components/layout/navbar';
import { ProcessingPage, VisualizationPage, AnalysisPage } from './pages';

export function App() {
  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <Navbar />
      <main className="flex-1 overflow-y-auto">
        <Router>
          <ProcessingPage path="/" />
          <VisualizationPage path="/visualization" />
          <AnalysisPage path="/analysis" />
        </Router>
      </main>
    </div>
  );
}
