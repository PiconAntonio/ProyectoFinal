from flask import Flask, render_template, jsonify
import paramiko
import socket
import psutil
import datetime

app = Flask(__name__)

# Definir las máquinas virtuales a monitorear
vms = [
    {"name": "web1", "ip": "10.0.0.33", "user": "ansible"},
    {"name": "web2", "ip": "10.0.0.34", "user": "ansible"}
]

def get_vm_info(vm):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(vm["ip"], username=vm["user"], timeout=3)

        # Obtener uptime
        stdin, stdout, stderr = ssh.exec_command("uptime")
        uptime_output = stdout.read().decode()

        # Obtener uso de memoria
        stdin, stdout, stderr = ssh.exec_command("free -m")
        free_output = stdout.read().decode()

        # Obtener espacio de disco
        stdin, stdout, stderr = ssh.exec_command("df -h /")
        disk_output = stdout.read().decode()

        # Obtener estadísticas de red
        stdin, stdout, stderr = ssh.exec_command("ifstat -i ens18 1 1")
        net_output = stdout.read().decode()

        ssh.close()

        # Procesar la salida del comando uptime
        cpu_load = uptime_output.split("load average:")[1].split(",")[0].strip()

        # Procesar la salida de free -m
        lines = free_output.splitlines()
        mem_line = lines[1].split()
        mem_total = int(mem_line[1])
        mem_used = int(mem_line[2])
        mem_percent = round(mem_used / mem_total * 100, 2)

        # Procesar la salida de df -h
        disk_line = disk_output.splitlines()[1].split()
        disk_available = disk_line[3]

        # Procesar estadísticas de red
        net_lines = net_output.splitlines()
        if len(net_lines) > 2:
            net_received, net_sent = net_lines[2].split()
        else:
            net_received, net_sent = ('0', '0')

        return {
            "status": "✅ OK",
            "cpu_load": cpu_load,
            "mem_percent": f"{mem_percent}%",
            "disk_available": disk_available,
            "net_received": net_received,
            "net_sent": net_sent,
            "uptime": uptime_output
        }
    except (socket.error, paramiko.ssh_exception.SSHException, IndexError, ValueError) as e:
        return {
            "status": "❌ Caído",
            "cpu_load": "-",
            "mem_percent": "-",
            "disk_available": "-",
            "net_received": "-",
            "net_sent": "-",
            "uptime": "-"
        }

@app.route('/')
def home():
    results = []
    for vm in vms:
        info = get_vm_info(vm)
        results.append({
            "name": vm["name"],
            "ip": vm["ip"],
            "status": info["status"],
            "cpu_load": info["cpu_load"],
            "mem_percent": info["mem_percent"],
            "disk_available": info["disk_available"],
            "net_received": info["net_received"],
            "net_sent": info["net_sent"],
            "uptime": info["uptime"]
        })
    return render_template("layout.html", vms=results)

@app.route('/api/data')
def api_data():
    data = {
        "cpu_load": [10, 20, 30, 40, 50],
        "mem_usage": [20, 30, 40, 50, 60],
        "network_in": [5, 10, 15, 20, 25],
        "network_out": [3, 6, 9, 12, 15]
    }
    return jsonify(data)

if __name__ == "__main__":
    # Cambia '127.0.0.1' por '0.0.0.0' para que escuche en todas las interfaces de red
    app.run(host="0.0.0.0", port=5000, debug=True)
