import argparse
import math
import time
from asyncua.sync import Client


def monitorizar_celda_opcua(endpoint="opc.tcp://127.0.0.1:4840/freeopcua/server/", num_iter=360):
    estados_vistos = []
    estado_anterior = None
    uri = "urn:freeopcua:python:server"

    print(f"Conectando cliente OPC UA a {endpoint}...")
    with Client(endpoint) as client:
        idx = client.get_namespace_index(uri)
        objects = client.get_objects_node()

        nodo_temp_amb = objects.get_child([f"{idx}:PlantaIndustrial", f"{idx}:Temperatura"])
        nodo_pos_x = objects.get_child([f"{idx}:Robot1", f"{idx}:R1Pos_x"])
        nodo_pos_y = objects.get_child([f"{idx}:Robot1", f"{idx}:R1Pos_y"])
        nodo_bat = objects.get_child([f"{idx}:Robot1", f"{idx}:Bateria"])
        nodo_temp_mot = objects.get_child([f"{idx}:Robot1", f"{idx}:TempMotor"])
        nodo_estado = objects.get_child([f"{idx}:Robot1", f"{idx}:Estado"])

        contador = 0
        try:
            while num_iter == 0 or contador < num_iter:
                # Simular temperatura ambiente (ej. ~21-25 C)
                temp_ambiente = round(22.5 + 1.5 * math.sin(contador * 0.2), 2)
                nodo_temp_amb.write_value(float(temp_ambiente))

                pos_x = nodo_pos_x.read_value()
                pos_y = nodo_pos_y.read_value()
                bat = nodo_bat.read_value()
                temp_mot = nodo_temp_mot.read_value()
                estado_actual = str(nodo_estado.read_value())

                estados_vistos.append(estado_actual)

                if estado_anterior is not None and estado_actual != estado_anterior:
                    print(f"[CAMBIO ESTADO] Robot1: {estado_anterior} -> {estado_actual}")
                estado_anterior = estado_actual

                print(
                    f"[OPC UA Cliente] T_amb={temp_ambiente}C | Robot1 pos=({pos_x}, {pos_y}) "
                    f"bat={bat}% temp_motor={temp_mot}C estado={estado_actual}"
                )

                contador += 1
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nCliente OPC UA detenido por el usuario.")

    return estados_vistos


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cliente OPC UA (sensor ambiental y lectura Robot1)")
    parser.add_argument("--port", type=int, default=4840)
    parser.add_argument("--num-iter", type=int, default=360)
    args = parser.parse_args()

    url = f"opc.tcp://127.0.0.1:{args.port}/freeopcua/server/"
    lista_estados = monitorizar_celda_opcua(endpoint=url, num_iter=args.num_iter)
    print(f"Total de lecturas de estado registradas: {len(lista_estados)}")
