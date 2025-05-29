import './commands';
import 'cypress-wait-until';

before(() => {
 // light-weight “is stack up?” probe
 cy.request({
   url: 'http://localhost:8081/api/books',
   failOnStatusCode: false   // don’t fail if the stack is still booting
 });
});