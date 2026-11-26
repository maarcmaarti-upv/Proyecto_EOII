import argparse
import time
from asyncua.sync import Server


class ServidorOPCUACelda:
    def __init__(self, endpoint="opc.tcp://127.0.0.1:4840/freeopcua/server/"):
        self.endpoint = endpoint
        self.server = Server()
        self.server.set_endpoint(self.endpoint)
        self.server.set_server_name("Servidor OPC UA Celda AGV EOII")

        uri = "urn:freeopcua:python:server"
        self.idx = self.server.register_namespace(uri)

        objects = self.server.get_objects_node()

        # Objeto PlantaIndustrial
        planta = objects.add_object(self.idx, "PlantaIndustrial")
        self.temperatura = planta.add_variable(self.idx, "Temperatura", 22.0)
        self.temperatura.set_writable()

        # Objeto Robot1
        robot1 = objects.add_object(self.idx, "Robot1")
        self.r1_pos_x = robot1.add_variable(self.idx, "R1Pos_x", 0.0)
        self.r1_pos_y = robot1.add_variable(self.idx, "R1Pos_y", 0.0)
        self.bateria = robot1.add_variable(self.idx, "Bateria", 100.0)
        self.temp_motor = robot1.add_variable(self.idx, "TempMotor", 25.0)
        self.estado = robot1.add_variable(self.idx, "Estado", "NORMAL")

        for var in (self.r1_pos_x, self.r1_pos_y, self.bateria, self.temp_motor, self.estado):
            var.set_writable()

    def iniciar(self, runtime=0):
        self.server.start()
        print(f"Servidor OPC UA activo en {self.endpoint} (namespace idx={self.idx})")
        inicio = time.time()
        try:
            while True:
                if runtime > 0 and (time.time() - inicio) >= runtime:
                    break
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nDeteniendo servidor OPC UA...")
        finally:
            self.server.stop()
            print("Servidor OPC UA detenido.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor OPC UA de la celda industrial")
    parser.add_argument("--port", type=int, default=4840)
    parser.add_argument("--runtime", type=int, default=0)
    args = parser.parse_args()

    url = f"opc.tcp://127.0.0.1:{args.port}/freeopcua/server/"
    servidor = ServidorOPCUACelda(endpoint=url)
    servidor.iniciar(runtime=args.runtime)
