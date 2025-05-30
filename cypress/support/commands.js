Cypress.Commands.add('placeOrder', payload => {
  return cy.request({
    method: 'POST',
    url: `${Cypress.env('API')}/checkout`,
    body: payload,
    failOnStatusCode: false   // we assert manually
  });
});

Cypress.Commands.add('restartBooksService', () => {
  // cy.exec('docker-compose restart books_0');
  // cy.exec('docker-compose restart books_1');
  // cy.exec('docker-compose restart books_2');
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
    Cypress.Promise.all(chainables.map(ch =>
      ch && typeof ch.then === 'function'
        ? new Cypress.Promise(resolve => ch.then(resolve))   // ← force real promise
        : Cypress.Promise.resolve(ch)
    )))
});


/**
 * Clicks the “Add to cart” button for a given book title `times` times.
 * Usage:  cy.addItem('Harry Potter', 2)
 */
// cypress/support/commands.js

Cypress.Commands.add('addItem', (title, qty = 1) => {
  // Find the <li> that contains the title text
  cy.contains('li', title, { timeout: 10_000 })   // ⬅ waits until list is rendered
    .find('input[type=number]')                   // the quantity input in that <li>
    .clear()
    .type(String(qty))
    .blur();                                      // trigger any onBlur handler
});


/**
 * Goes through the checkout UI with the same fixture shape
 * you used for the API flow.
 * Usage:  cy.checkout(orders.happy)
 */
// cypress/support/commands.js
Cypress.Commands.add('checkout', order => {
  const p = order.payload;                 // shorthand

  // ──────────────────────────────────────────
  // USER + PAYMENT
  cy.get('[name=name]').clear().type(p.user.name);
  cy.get('[name=contact]').clear().type(p.user.contact);

  cy.get('[name=creditCard]').clear().type(p.creditCard.number);
  cy.get('[name=expirationDate]').clear().type(p.creditCard.expirationDate);
  cy.get('[name=cvv]').clear().type(p.creditCard.cvv);

  // ──────────────────────────────────────────
  // ADDRESS
  cy.get('[name=billingStreet]').type(p.billingAddress.street);
  cy.get('[name=billingCity]').type(p.billingAddress.city);
  cy.get('[name=billingState]').type(p.billingAddress.state);
  cy.get('[name=billingZip]').type(p.billingAddress.zip);
  cy.get('[name=billingCountry]').type(p.billingAddress.country);

  // ──────────────────────────────────────────
  // SHIPPING + EXTRAS
  cy.get('[name=shippingMethod]').select(p.shippingMethod);
  cy.get('[name=giftWrapping]')[p.giftWrapping ? 'check' : 'uncheck']();
  cy.get('[name=terms]').check();

  // ──────────────────────────────────────────
  // SUBMIT
  cy.contains('button', /submit order/i).click();
});
