import argparse
import json
import socket
import time
from asyncua.sync import Client
import paho.mqtt.client as mqtt


def crear_cliente_mqtt(client_id=""):
    try:
        from paho.mqtt.enums import CallbackAPIVersion
        return mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION1, client_id=client_id)
    except (ImportError, AttributeError):
        return mqtt.Client(client_id=client_id)


class GatewayBridge:
    def __init__(
        self,
        host="127.0.0.1",
        udp_port=3000,
        tcp_port=5000,
        mqtt_port=1883,
        opcua_port=4840,
        mqtt_topic="planta1/celda1/robots/telemetria",
    ):
        self.host = host
        self.udp_port = udp_port
        self.tcp_port = tcp_port
        self.mqtt_port = mqtt_port
        self.opcua_port = opcua_port
        self.mqtt_topic = mqtt_topic

        # Socket UDP entrante
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.bind((self.host, self.udp_port))
        self.udp_sock.settimeout(1.0)

        # Conexiones persistentes
        self.tcp_sock = None
        self.tcp_reader = None
        self.mqtt_client = None
        self.opcua_client = None
        self.opcua_nodes = {}

    def conectar_tcp(self):
        try:
            self.cerrar_tcp()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect((self.host, self.tcp_port))
            self.tcp_sock = sock
            self.tcp_reader = sock.makefile("r", encoding="utf-8")
            print(f"[Bridge] Conectado a TCP {self.host}:{self.tcp_port}")
        except OSError as exc:
            print(f"[Bridge] Aviso: no se pudo conectar a TCP ({exc})")
            self.cerrar_tcp()

    def cerrar_tcp(self):
        if self.tcp_reader is not None:
            try:
                self.tcp_reader.close()
            except OSError:
                pass
            self.tcp_reader = None
        if self.tcp_sock is not None:
            try:
                self.tcp_sock.close()
            except OSError:
                pass
            self.tcp_sock = None

    def consultar_tcp(self, trama):
        if self.tcp_sock is None or self.tcp_reader is None:
            self.conectar_tcp()

        if self.tcp_sock is None or self.tcp_reader is None:
            return "SIN_EVALUAR"

        try:
            mensaje = (json.dumps(trama) + "\n").encode("utf-8")
            self.tcp_sock.sendall(mensaje)
            linea = self.tcp_reader.readline()
            if not linea:
                raise OSError("Respuesta TCP vacia")

            resp = json.loads(linea)
            if resp.get("status") == "ACK" and "server_status" in resp:
                return resp["server_status"]
            return "SIN_EVALUAR"
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[Bridge] Aviso en consulta TCP ({exc}) -> SIN_EVALUAR")
            self.cerrar_tcp()
            return "SIN_EVALUAR"

    def conectar_mqtt(self):
        try:
            client = crear_cliente_mqtt()
            client.connect(self.host, self.mqtt_port, 60)
            client.loop_start()
            self.mqtt_client = client
            print(f"[Bridge] Conectado a MQTT {self.host}:{self.mqtt_port}")
        except Exception as exc:
            print(f"[Bridge] Aviso: no se pudo conectar a MQTT ({exc})")
            self.mqtt_client = None

    def publicar_mqtt(self, trama_enriquecida):
        if self.mqtt_client is None:
            self.conectar_mqtt()
        if self.mqtt_client is not None:
            try:
                self.mqtt_client.publish(
                    self.mqtt_topic,
                    json.dumps(trama_enriquecida),
                    qos=1,
                )
            except Exception as exc:
                print(f"[Bridge] Aviso al publicar en MQTT ({exc})")

    def conectar_opcua(self):
        endpoint = f"opc.tcp://{self.host}:{self.opcua_port}/freeopcua/server/"
        uri = "urn:freeopcua:python:server"
        try:
            client = Client(endpoint)
            client.connect()
            idx = client.get_namespace_index(uri)
            objects = client.get_objects_node()
            self.opcua_client = client
            self.opcua_nodes = {
                "R1Pos_x": objects.get_child([f"{idx}:Robot1", f"{idx}:R1Pos_x"]),
                "R1Pos_y": objects.get_child([f"{idx}:Robot1", f"{idx}:R1Pos_y"]),
                "Bateria": objects.get_child([f"{idx}:Robot1", f"{idx}:Bateria"]),
                "TempMotor": objects.get_child([f"{idx}:Robot1", f"{idx}:TempMotor"]),
                "Estado": objects.get_child([f"{idx}:Robot1", f"{idx}:Estado"]),
            }
            print(f"[Bridge] Conectado a OPC UA {endpoint}")
        except Exception as exc:
            print(f"[Bridge] Aviso: no se pudo conectar a OPC UA ({exc})")
            self.opcua_client = None
            self.opcua_nodes = {}

    def escribir_opcua(self, trama_enriquecida):
        if not self.opcua_nodes:
            self.conectar_opcua()
        if not self.opcua_nodes:
            return

        try:
            self.opcua_nodes["R1Pos_x"].write_value(float(trama_enriquecida.get("pos_x", 0.0)))
            self.opcua_nodes["R1Pos_y"].write_value(float(trama_enriquecida.get("pos_y", 0.0)))
            self.opcua_nodes["Bateria"].write_value(float(trama_enriquecida.get("battery", 0.0)))
            self.opcua_nodes["TempMotor"].write_value(float(trama_enriquecida.get("temp_motor", 0.0)))
            self.opcua_nodes["Estado"].write_value(str(trama_enriquecida.get("server_status", "SIN_EVALUAR")))
        except Exception as exc:
            print(f"[Bridge] Aviso al escribir en OPC UA ({exc})")
            try:
                if self.opcua_client is not None:
                    self.opcua_client.disconnect()
            except Exception:
                pass
            self.opcua_client = None
            self.opcua_nodes = {}

    def ejecutar(self, num_iter=360):
        print(f"Gateway Bridge escuchando UDP en {self.host}:{self.udp_port} (--num-iter={num_iter})")
        self.conectar_tcp()
        self.conectar_mqtt()
        self.conectar_opcua()

        procesadas = 0
        try:
            while num_iter == 0 or procesadas < num_iter:
                try:
                    data, _ = self.udp_sock.recvfrom(4096)
                except socket.timeout:
                    continue

                try:
                    trama = json.loads(data.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    print("[Bridge] Datagrama UDP no valido descartado.")
                    continue

                # 1. Consultar estado al servidor TCP
                server_status = self.consultar_tcp(trama)

                # 2. Enriquecer trama
                trama_enriquecida = dict(trama)
                trama_enriquecida["server_status"] = server_status

                # 3. Difundir por MQTT y escribir en OPC UA
                self.publicar_mqtt(trama_enriquecida)
                self.escribir_opcua(trama_enriquecida)

                procesadas += 1
                print(
                    f"[Bridge #{procesadas}] seq={trama_enriquecida.get('seq')} "
                    f"server_status={server_status} -> MQTT & OPC UA"
                )
        except KeyboardInterrupt:
            print("\nGateway Bridge detenido por el usuario.")
        finally:
            self.cerrar()

    def cerrar(self):
        self.udp_sock.close()
        self.cerrar_tcp()
        if self.mqtt_client is not None:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception:
                pass
        if self.opcua_client is not None:
            try:
                self.opcua_client.disconnect()
            except Exception:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pasarela de integracion UDP -> TCP -> MQTT -> OPC UA")
    parser.add_argument("--udp-port", type=int, default=3000)
    parser.add_argument("--tcp-port", type=int, default=5000)
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--opcua-port", type=int, default=4840)
    parser.add_argument("--num-iter", type=int, default=360)
    args = parser.parse_args()

    bridge = GatewayBridge(
        host="127.0.0.1",
        udp_port=args.udp_port,
        tcp_port=args.tcp_port,
        mqtt_port=args.mqtt_port,
        opcua_port=args.opcua_port,
    )
    bridge.ejecutar(num_iter=args.num_iter)
