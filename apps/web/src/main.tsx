import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { A06Review } from './A06Review';
import { App } from './App';
import './styles.css';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Root element not found');
}

const reviewMode =
  new URLSearchParams(window.location.search).get('a06-review') === '1';

createRoot(rootElement).render(
  <StrictMode>{reviewMode ? <A06Review /> : <App />}</StrictMode>,
);
