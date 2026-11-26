import argparse
import json
import socket
import threading


def evaluate_status(trama):
    """Evalua las reglas de control (ALARM_HIGH_TEMP tiene prioridad)."""
    temp_motor = float(trama.get("temp_motor", 0.0))
    battery = float(trama.get("battery", 100.0))

    if temp_motor > 40.0:
        return "ALARM_HIGH_TEMP"
    if battery < 20.0:
        return "ALARM_LOW_BATTERY"
    return "NORMAL"


def send_json(conn, payload):
    """Envia un diccionario JSON terminado en salto de linea por el socket."""
    mensaje = (json.dumps(payload) + "\n").encode("utf-8")
    conn.sendall(mensaje)


def client_handler_thread(conn, addr, num_iter=0):
    """Atiende a un unico cliente en su propio hilo usando su socket y variables locales."""
    print(f"[TCP] Cliente conectado desde {addr}")
    atendidas = 0

    try:
        with conn, conn.makefile("r", encoding="utf-8") as lector:
            for linea in lector:
                linea = linea.strip()
                if not linea:
                    continue

                try:
                    trama = json.loads(linea)
                    server_status = evaluate_status(trama)
                    ack = {
                        "status": "ACK",
                        "robot_id": trama.get("robot_id", "DESCONOCIDO"),
                        "seq": trama.get("seq", -1),
                        "server_status": server_status,
                    }
                    send_json(conn, ack)
                    print(f"[TCP {addr}] seq={ack['seq']} -> {server_status}")
                except (json.JSONDecodeError, TypeError, ValueError):
                    nack = {"status": "NACK", "reason": "INVALID_JSON"}
                    send_json(conn, nack)
                    print(f"[TCP {addr}] Trama invalida -> NACK")

                atendidas += 1
                if num_iter > 0 and atendidas >= num_iter:
                    break
    except OSError as exc:
        print(f"[TCP {addr}] Conexion cerrada: {exc}")
    finally:
        print(f"[TCP] Hilo finalizado para {addr}")


def run_application(host="127.0.0.1", port=5000, num_iter=360):
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind((host, port))
    servidor.listen(10)
    servidor.settimeout(1.0)

    print(f"Servidor TCP concurrente escuchando en {host}:{port} (--num-iter={num_iter})")
    hilos = []

    try:
        while True:
            try:
                conn, addr = servidor.accept()
            except socket.timeout:
                continue

            hilo = threading.Thread(
                target=client_handler_thread,
                args=(conn, addr, num_iter),
                daemon=True,
            )
            hilo.start()
            hilos.append(hilo)
    except KeyboardInterrupt:
        print("\nDeteniendo servidor TCP...")
    finally:
        servidor.close()
        for h in hilos:
            h.join(timeout=1.0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor TCP concurrente de control")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--num-iter", type=int, default=360)
    args = parser.parse_args()

    run_application(host="127.0.0.1", port=args.port, num_iter=args.num_iter)
