// single_happy.cy.js  (spec file)
import orders from '../../cypress/fixtures/orders.json';

const o = orders.happy;

it('submits via UI and deducts stock', () => {

  // 1️⃣ put the spy in place **first**
  cy.intercept('GET', '**/api/books').as('getBooks');

  // 2️⃣ load the storefront
  cy.visit('/');

  // 3️⃣ wait until the catalogue has come back
  cy.wait('@getBooks');

  // 4️⃣ now interact with the page
  cy.addItem('Harry Potter', 2);
  cy.checkout(o);

  cy.contains('Order Approved');

  // back-end verification
  cy.request(`${Cypress.env('API')}/api/books`)
    .its('body')
    .then(list => {
      const hp = list.find(b => b.title === 'Harry Potter');
      expect(hp.stock).to.eq(o.expectedStockAfter);
    });
});
