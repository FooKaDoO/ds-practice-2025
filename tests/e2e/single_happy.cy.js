import orders from '../../cypress/fixtures/orders.json';
const o = orders.happy;

it('submits via UI and deducts stock', () => {
  cy.restartBooksService().then(() => {

    cy.intercept('GET', '**/api/books').as('getBooks');
    cy.visit('/');
    cy.wait('@getBooks');
  
    cy.addItem('Harry Potter', 2);   // ← now finds the input
    cy.checkout(o);                  // Submit Order button works fine
  
    cy.contains(/order placed/i);  // case-insensitive just in case

  });

});
