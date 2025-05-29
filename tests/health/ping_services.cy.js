// tests/health/ping_services.cy.js
const endpoints = [
  '/api/books',
  '/status/fraud_detection',
  '/status/transaction_verification',
  '/status/order_queue'
];
endpoints.forEach(ep => {
  it(`responds 200 for ${ep}`, () => {
    cy.request(`${Cypress.env('API')}${ep}`).its('status').should('eq', 200);
  });
});
