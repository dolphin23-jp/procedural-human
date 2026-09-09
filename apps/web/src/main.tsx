import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { A06Review } from './A06Review';
import { A07VesselIdentification } from './A07VesselIdentification';
import { App } from './App';
import './styles.css';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Root element not found');
}

const searchParams = new URLSearchParams(window.location.search);
const a06ReviewMode = searchParams.get('a06-review') === '1';
const a07IdentificationMode =
  searchParams.get('a07-vessel-identification') === '1';

const content = a07IdentificationMode ? (
  <A07VesselIdentification />
) : a06ReviewMode ? (
  <A06Review />
) : (
  <App />
);

createRoot(rootElement).render(<StrictMode>{content}</StrictMode>);
