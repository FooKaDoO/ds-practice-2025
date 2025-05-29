describe('Conflicting orders racing for the same stock', () => {

  it('allows only one order to commit', () => {

    const order = qty => ({
      user:{ name:'Race', contact:'race@test' },
      creditCard:{ number:'4111111111111111', expirationDate:'12/25', cvv:'123' },
      items:[{ name:'Harry Potter', quantity:qty }],
      billingAddress:{ street:'x', city:'x', state:'x', zip:'x', country:'EE' },
      shippingMethod:'Standard', giftWrapping:false, termsAccepted:true
    });

    cy.stockOf('Harry Potter').then(start => {

      // two orders for all remaining stock – only one should succeed
      const o1 = cy.placeOrder(order(start));
      const o2 = cy.placeOrder(order(start));

      cy.all(o1, o2, { timeout: 20_000 }).then(([r1, r2]) => {
        expect([r1.status, r2.status].filter(s => s === 200)).to.have.length(1);
        expect([r1.status, r2.status].filter(s => s === 400)).to.have.length(1);
      });

      // final book stock ↓ by exactly START
      cy.stockOf('Harry Potter')
        .should('eq', start - start);
    });
  });
});
