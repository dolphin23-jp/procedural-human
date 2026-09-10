import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { A06Review } from './A06Review';
import { AS05SourceNavigator } from './AS05SourceNavigator';
import { App } from './App';
import './styles.css';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Root element not found');
}

const params = new URLSearchParams(window.location.search);
const sourceNavigationMode = params.get('as05-source') === '1';
const reviewMode = params.get('a06-review') === '1';

createRoot(rootElement).render(
  <StrictMode>
    {sourceNavigationMode ? (
      <AS05SourceNavigator />
    ) : reviewMode ? (
      <A06Review />
    ) : (
      <App />
    )}
  </StrictMode>,
);
