import Router from 'preact-router';
import { Navbar } from './components/layout/navbar';
import { ProcessingPage, VisualizationPage, AnalysisPage } from './pages';

export function App() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>
        <Router>
          <ProcessingPage path="/" />
          <VisualizationPage path="/visualization" />
          <AnalysisPage path="/analysis" />
        </Router>
      </main>
    </div>
  );
}
