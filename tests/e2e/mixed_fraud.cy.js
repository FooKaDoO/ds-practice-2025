import orders from '../../cypress/fixtures/orders.json';

const good = orders.happy.payload;
const bad  = orders.fraud.payload;

describe('Mixture of fraudulent and normal orders', () => {

  it('accepts the good one, rejects the bad one', () => {

    // remember the catalog value _before_ we place anything
    cy.stockOf('Harry Potter').then(before => {

      cy.placeOrder(good).its('status').should('eq', 200);
      cy.placeOrder(bad ).its('status').should('eq', 400);

      const target = before - good.items[0].quantity;   // before-2
      cy.log(`Waiting until stock reaches ${target}`);

      cy.waitUntil(() =>
        cy.stockOf('Harry Potter').then(s => s === target),
        { timeout: 15_000, interval: 1_000 }            // 15 s max
      );

      // final assertions ──────────────────────────────
      cy.stockOf('Harry Potter').should('eq', target);
    });
  });

});
