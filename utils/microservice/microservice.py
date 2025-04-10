class MicroService:
    _static_microservice_index = 0
    _static_microservices = []
    # Total count of microservices is the same as _static_microservice_index

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.idx = MicroService._static_microservice_index
        self.orders = dict()
        MicroService._static_microservice_index += 1
        MicroService._static_microservices.append(self)
        for microservice in MicroService._static_microservices:
            microservice._update_length_of_vector_clocks()
    
    def init_order(self, order_id, order_data):
        self.orders[order_id] = {
            "order_data": order_data,
            "vc": [0]*MicroService._static_microservice_index
        }
    
    def increment(self, order_id: str, incoming_vc=None):
        entry = self.orders.get(order_id)
        if not entry:
            raise Exception(f"Order by {order_id} not found!")
        
        local_vc = entry["vc"]
        
        local_vc[self.idx] += 1
        if not incoming_vc:
            return None
        
        for i in range(MicroService._static_microservice_index):
            local_vc[i] = max(local_vc[i], incoming_vc[i])

    def depends_on(self, order_id, incoming_vc):
        """ vc1 > vc2 """
        entry = self.orders.get(order_id)
        if not entry:
            raise Exception(f"Order by {order_id} not found!")
        
        local_vc = entry["vc"]

        less, greater = False, False

        for i in range(MicroService._static_microservice_index):
            if local_vc[i] < incoming_vc[i]:
                less = True
            elif local_vc[i] > incoming_vc[i]:
                greater = True
        
        return not less and greater

    def _update_length_of_vector_clocks(self):
        for data in self.orders.values():
            vc = data["vc"]
            diff = MicroService._static_microservice_index - len(vc)
            if diff > 0:
                data["vc"] = vc + [0]*diff
    
    def _remove_vector_clock_at_idx(self, idx: int):
        for data in self.orders.values():
            data["vc"] = data["vc"].pop(idx)
    
    def __del__(self):
        MicroService._static_microservice_index -= 1
        MicroService._static_microservices.pop(self.idx)
        for microservice in MicroService._static_microservices[self.idx:]:
            microservice._remove_vector_clock_at_idx(self.idx)
            microservice.idx -= 1