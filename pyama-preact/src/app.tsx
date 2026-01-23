import Router from 'preact-router';
import { Navbar } from './components/layout/navbar';
import { ProcessingPage, VisualizationPage, AnalysisPage } from './pages';

export function App() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <Navbar />
      <main className="max-w-7xl mx-auto">
        <Router>
          <ProcessingPage path="/" />
          <VisualizationPage path="/visualization" />
          <AnalysisPage path="/analysis" />
        </Router>
      </main>
    </div>
  );
}
