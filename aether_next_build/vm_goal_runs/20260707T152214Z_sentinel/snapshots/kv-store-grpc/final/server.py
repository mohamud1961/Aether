import logging
from concurrent import futures

import grpc

import kv_store_pb2 as kv_store__pb2
import kv_store_pb2_grpc as kv_store__pb2_grpc


class Server(kv_store__pb2_grpc.KVStoreServicer):
    def __init__(self):
        self.store = {}

    def GetVal(self, request, context):
        return kv_store__pb2.GetValResponse(val=self.store.get(request.key, 0))

    def SetVal(self, request, context):
        self.store[request.key] = request.val
        return kv_store__pb2.SetValResponse(val=request.val)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    kv_store__pb2_grpc.add_KVStoreServicer_to_server(Server(), server)
    server.add_insecure_port('[::]:5328')
    server.start()
    logging.info('KVStore server listening on port 5328')
    server.wait_for_termination()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    serve()
