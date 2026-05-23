import { get } from './client.js';

export function listReports() {
  return get('/api/reports');
}

export function fetchReport(name) {
  return get(`/api/reports/${encodeURIComponent(name)}`);
}

export function reportPdfUrl(name) {
  return `/api/reports/${encodeURIComponent(name)}/pdf`;
}

export function downloadReportPdf(name) {
  window.open(reportPdfUrl(name), '_blank');
}
