import orders from '../../cypress/fixtures/orders.json';

describe('Two simultaneous non-conflicting orders', () => {

  it('both succeed and adjust their respective stocks', () => {

    const a = orders.happy;                       // buys Harry Potter (2)

    const b = {                                   // buys Twilight (1)
      ...orders.happy,
      payload: {
        ...orders.happy.payload,
        items: [{ name: 'Twilight', quantity: 1 }]
      }
    };

    // grab initial stocks
    cy.all(
      cy.stockOf('Harry Potter'),
      cy.stockOf('Twilight')
    ).then(([hp0, tw0]) => {

      // fire the two orders "in parallel"
    cy.all(
      cy.placeOrder(a.payload).then(r => r.status),   // returns 200
      cy.placeOrder(b.payload).then(r => r.status),   // returns 200
      { timeout: 20_000 }
    ).then(([stA, stB]) => {        // ← destructure, a bit clearer
      expect(stA).to.eq(200);
      expect(stB).to.eq(200);
    });

    });
  });

});
