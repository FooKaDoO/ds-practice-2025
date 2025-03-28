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
    
    def merge_and_increment(self, local_vc, incoming_vc):
        for i in range(MicroService._static_microservice_index):
            local_vc[i] = max(local_vc[i], incoming_vc[i])
        local_vc[self.idx] += 1
    
    def verify_items(self, order_id, incoming_vc):
        entry = self.orders.get(order_id)
        self.merge_and_increment(entry["vc"], incoming_vc)
        if not entry["data"].items():
            return {"fail": True, "vc": entry["vc"]}
        return {"fail": False, "vc": entry["vc"]}

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