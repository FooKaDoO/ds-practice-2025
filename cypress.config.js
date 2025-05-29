import { defineConfig } from 'cypress';

export default defineConfig({
  e2e: {
    baseUrl: 'http://localhost:8080',
    specPattern: 'tests/e2e/**/*.cy.js',   // stays the same
    supportFile: 'cypress/support/e2e.js',
    video: false,
  },
   env: {
    API: 'http://localhost:8081'               // ← Orchestrator/REST port
  }
});
