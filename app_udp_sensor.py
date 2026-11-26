import argparse
import json
import random
import socket
import time
from datetime import datetime


class SimuladorAGV:
    def __init__(self, robot_id="ROBOT_AGV_01"):
        self.robot_id = robot_id
        self.seq = 0
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.battery = 85.0
        self.temp_motor = 34.0
        self.status = "MOVING"
        self._dir_x = 0.45
        self._dir_y = 0.25

    def actualizar_estado(self):
        self.seq += 1

        # Gestion de estados MOVING / IDLE / CHARGING del sensor
        if self.status == "CHARGING":
            self.battery = min(95.0, round(self.battery + 3.5, 2))
            self.temp_motor = max(28.0, round(self.temp_motor - 0.8, 2))
            if self.battery >= 95.0:
                self.status = "MOVING"
        elif self.battery < 15.0:
            self.status = "CHARGING"
        elif random.random() < 0.15:
            self.status = "IDLE"
        else:
            self.status = "MOVING"

        if self.status == "MOVING":
            self.pos_x = round((self.pos_x + self._dir_x) % 20.0, 2)
            self.pos_y = round((self.pos_y + self._dir_y) % 20.0, 2)
            self.battery = max(0.0, round(self.battery - 0.6, 2))
            delta_temp = random.uniform(-0.5, 1.4)
            self.temp_motor = round(max(25.0, min(52.0, self.temp_motor + delta_temp)), 2)
        elif self.status == "IDLE":
            self.battery = max(0.0, round(self.battery - 0.1, 2))
            self.temp_motor = round(max(25.0, self.temp_motor - 0.4), 2)

    def generar_trama(self):
        self.actualizar_estado()
        return {
            "robot_id": self.robot_id,
            "seq": self.seq,
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "pos_x": self.pos_x,
            "pos_y": self.pos_y,
            "battery": self.battery,
            "temp_motor": self.temp_motor,
            "status": self.status,
        }


def emitir_telemetria(host="127.0.0.1", port=3000, scada_port=3001, num_iter=360):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bridge_addr = (host, port)
    scada_addr = (host, scada_port) if scada_port and scada_port > 0 else None
    agv = SimuladorAGV()

    print(f"Sensor UDP iniciado -> {bridge_addr} (SCADA: {scada_addr}, iteraciones: {num_iter})")

    contador = 0
    try:
        while num_iter == 0 or contador < num_iter:
            trama = agv.generar_trama()
            payload = json.dumps(trama).encode("utf-8")

            udp_socket.sendto(payload, bridge_addr)
            if scada_addr is not None:
                udp_socket.sendto(payload, scada_addr)

            print(
                f"[UDP] seq={trama['seq']} pos=({trama['pos_x']}, {trama['pos_y']}) "
                f"bat={trama['battery']}% temp={trama['temp_motor']}C estado={trama['status']}"
            )

            contador += 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nSensor UDP detenido por el usuario.")
    finally:
        udp_socket.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulador de sensor UDP para AGV")
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--scada-port", type=int, default=3001)
    parser.add_argument("--num-iter", type=int, default=360)
    args = parser.parse_args()

    emitir_telemetria(
        host="127.0.0.1",
        port=args.port,
        scada_port=args.scada_port,
        num_iter=args.num_iter,
    )
