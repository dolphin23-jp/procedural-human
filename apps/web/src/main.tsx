import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { A06Review } from './A06Review';
import { AS05SourceNavigator } from './AS05SourceNavigator';
import { App } from './App';
import { M8VAdjudication } from './M8VAdjudication';
import { M8VReview } from './M8VReview';
import './styles.css';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Root element not found');
}

const params = new URLSearchParams(window.location.search);
const sourceNavigationMode = params.get('as05-source') === '1';
const reviewMode = params.get('a06-review') === '1';
const vesselEvidenceReviewMode = params.get('m8v-review') === '1';
const vesselAdjudicationMode = params.get('m8v-adjudicate') === '1';

createRoot(rootElement).render(
  <StrictMode>
    {sourceNavigationMode ? (
      <AS05SourceNavigator />
    ) : reviewMode ? (
      <A06Review />
    ) : vesselAdjudicationMode ? (
      <M8VAdjudication />
    ) : vesselEvidenceReviewMode ? (
      <M8VReview />
    ) : (
      <App />
    )}
  </StrictMode>,
);
