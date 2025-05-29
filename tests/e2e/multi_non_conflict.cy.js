import orders from '../fixtures/orders.json';

describe('Two simultaneous non-conflicting orders', () => {

  it('both succeed and adjust their respective stocks', () => {
    const a = orders.happy;                         // buys Harry Potter
    const b = { ...orders.happy,                    // clone & tweak
      items: [{ name: 'Twilight', quantity: 1 }]
    };

    // capture starting stocks
    let hp0, tw0;
    cy.stockOf('Harry Potter').then(s => hp0 = s);
    cy.stockOf('Twilight').then(s => tw0 = s);

    // fire the two orders “at once”
    cy.wrap(null).then(() => {
      cy.placeOrder(a.payload).its('status').should('eq', 200);
      cy.placeOrder(b).its('status').should('eq', 200);
    });

    // final assertion
    cy.stockOf('Harry Potter').should('eq', hp0 - 2);
    cy.stockOf('Twilight').should('eq',  tw0 - 1);
  });

});
