import argparse
import json
import time
import paho.mqtt.client as mqtt


def crear_cliente_mqtt(client_id=""):
    try:
        from paho.mqtt.enums import CallbackAPIVersion
        return mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION1, client_id=client_id)
    except (ImportError, AttributeError):
        return mqtt.Client(client_id=client_id)


class MonitorMQTT:
    def __init__(self, topic_filtro="planta1/celda1/robots/+"):
        self.topic_filtro = topic_filtro
        self.total_mensajes = 0
        self.total_alarmas = 0

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"[MQTT] Conectado al broker. Suscrito a '{self.topic_filtro}'")
            client.subscribe(self.topic_filtro, qos=1)
        else:
            print(f"[MQTT] Error de conexion (rc={rc})")

    def on_message(self, client, userdata, msg):
        self.total_mensajes += 1
        raw = msg.payload.decode("utf-8", errors="replace")

        try:
            datos = json.loads(raw)
            robot_id = datos.get("robot_id", "ROBOT_AGV_01")
            seq = datos.get("seq", "?")
            server_status = datos.get("server_status", "SIN_EVALUAR")
            temp_motor = datos.get("temp_motor", "?")
            battery = datos.get("battery", "?")

            print(
                f"[{msg.topic}] robot={robot_id} seq={seq} "
                f"estado={server_status} bat={battery}% temp={temp_motor}C"
            )

            if isinstance(server_status, str) and server_status.startswith("ALARM_"):
                self.total_alarmas += 1
                print(f"[ALARMA] {robot_id} seq={seq} {server_status} temp_motor={temp_motor}C")
        except json.JSONDecodeError:
            print(f"[{msg.topic}] {raw}")


def ejecutar_monitor(host="127.0.0.1", port=1883, topic="planta1/celda1/robots/+", num_iter=360):
    monitor = MonitorMQTT(topic_filtro=topic)
    client = crear_cliente_mqtt()
    client.on_connect = monitor.on_connect
    client.on_message = monitor.on_message

    client.connect(host, port, 60)
    inicio = time.time()
    duracion_max = num_iter * 0.5 if num_iter > 0 else None

    try:
        while True:
            client.loop(timeout=0.2)
            if duracion_max is not None and (time.time() - inicio) >= duracion_max:
                break
    except KeyboardInterrupt:
        print("\nMonitor MQTT detenido por el usuario.")
    finally:
        client.disconnect()
        print(
            f"Resumen MQTT -> Mensajes recibidos: {monitor.total_mensajes} | "
            f"Alarmas detectadas: {monitor.total_alarmas}"
        )


def ejecutar_publicador(host="127.0.0.1", port=1883, topic="planta1/celda1/robots/telemetria", num_iter=10):
    client = crear_cliente_mqtt()
    client.connect(host, port, 60)
    client.loop_start()
    try:
        for i in range(1, num_iter + 1):
            payload = json.dumps({"robot_id": "ROBOT_AGV_01", "seq": i, "server_status": "NORMAL"})
            client.publish(topic, payload, qos=1)
            time.sleep(0.5)
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor/Publicador MQTT para telemetria")
    parser.add_argument("--mode", type=str, default="sub", choices=["sub", "pub"])
    parser.add_argument("--num-iter", type=int, default=360)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    args = parser.parse_args()

    if args.mode == "pub":
        ejecutar_publicador(host=args.host, port=args.port, num_iter=args.num_iter)
    else:
        ejecutar_monitor(host=args.host, port=args.port, num_iter=args.num_iter)
