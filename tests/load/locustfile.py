from locust import HttpUser, task, between
import random, uuid, json

BOOKS = ["Harry Potter","Twilight","Lord of the Rings","Clean Code"]

class Shopper(HttpUser):
    wait_time = between(1, 3)

    @task
    def checkout(self):
        payload = {
            "user": {"name":"Load Bot","contact":"bot@locust.io"},
            "creditCard":{"number":"4111111111111111","expirationDate":"12/30","cvv":"999"},
            "items":[{"name": random.choice(BOOKS), "quantity": 1}],
            "billingAddress": {
                "street":"Nowhere 1","city":"NA","state":"NA",
                "zip":"00000","country":"Testland"
            },
            "shippingMethod":"Standard",
            "giftWrapping":False,
            "termsAccepted":True
        }
        self.client.post("/checkout", json=payload, name="/checkout")
