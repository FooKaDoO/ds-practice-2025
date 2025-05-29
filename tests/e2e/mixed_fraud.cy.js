import orders from '../../cypress/fixtures/orders.json';

const good = orders.happy.payload;
const bad  = orders.fraud.payload;

describe('Mixture of fraudulent and normal orders', () => {

  it('accepts the good one, rejects the bad one', () => {
    
    cy.restartBooksService().then(() => {
      cy.stockOf('Harry Potter').then(stockBefore => {

        cy.placeOrder(bad ).its('status').should('eq', 400);
        cy.placeOrder(good).its('status').should('eq', 200);
        cy.placeOrder(bad ).its('status').should('eq', 400);
        cy.placeOrder(good).its('status').should('eq', 200);
  
        const target = stockBefore - 2*good.items[0].quantity;   // before-2
        cy.log(`Waiting until stock reaches ${target}`);
  
        cy.waitUntil(() =>
          cy.stockOf('Harry Potter').then(s => (s + 0) === target),
          { timeout: 20_000, interval: 1_000 }            // 15 s max
        );
  
      });
    });
    
  });

});
