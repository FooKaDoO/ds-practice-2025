Cypress.Commands.add('placeOrder', payload => {
  return cy.request({
    method: 'POST',
    url: `${Cypress.env('API')}/checkout`,
    body: payload,
    failOnStatusCode: false   // we assert manually
  });
});

Cypress.Commands.add('stockOf', title =>
  cy.request(`${Cypress.env('API')}/api/books`)
    .its('body')
    .then(list => list.find(b => b.title === title).stock)
);

Cypress.Commands.add('all', (...chainables) => {
  const opts = typeof chainables[chainables.length - 1] === 'object'
             ? chainables.pop() : {};
  const timeout  = opts.timeout || Cypress.config('defaultCommandTimeout');

  // 👇 **return** the promise so callers receive the array
  return cy.wrap(
    Cypress.Promise.all(chainables.map(ch => ch.then ? ch : cy.wrap(ch))),
    { timeout }
  );
});


/**
 * Clicks the “Add to cart” button for a given book title `times` times.
 * Usage:  cy.addItem('Harry Potter', 2)
 */
// cypress/support/commands.js
Cypress.Commands.add('addItem', (title, qty = 1) => {
  // purely DOM interaction, no waits
  cy.contains(title)
    .parent()                         // adjust to book row/card
    .find('input[type=number]')       // quantity box
    .clear()
    .type(String(qty));
});



/**
 * Goes through the checkout UI with the same fixture shape
 * you used for the API flow.
 * Usage:  cy.checkout(orders.happy)
 */
Cypress.Commands.add('checkout', order => {
  const p = order.payload;          // just shorter names
  cy.contains('Cart').click();
  cy.contains('Checkout').click();

  // user details
  cy.get('[name=name]').type(p.user.name);
  cy.get('[name=contact]').type(p.user.contact);

  // credit-card
  cy.get('[name=cc-number]').type(p.creditCard.number);
  cy.get('[name=cc-exp]').type(p.creditCard.expirationDate);
  cy.get('[name=cc-cvv]').type(p.creditCard.cvv);

  // address
  cy.get('[name=street]').type(p.billingAddress.street);
  cy.get('[name=city]').type(p.billingAddress.city);
  cy.get('[name=state]').type(p.billingAddress.state);
  cy.get('[name=zip]').type(p.billingAddress.zip);
  cy.get('[name=country]').select(p.billingAddress.country);

  // extras
  cy.get('[name=shipping]').select(p.shippingMethod);
  if (p.giftWrapping) cy.get('[name=giftWrapping]').check();
  cy.get('[name=terms]').check();

  cy.contains('Place order').click();
});