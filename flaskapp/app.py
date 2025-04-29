from flask import Flask, render_template, redirect
import paramiko
import socket

app = Flask(__name__)

vms = [
    {
        "name": "web1",
        "ip": "10.0.0.33",
        "user": "ansible",
        "password": "tu_clave",
        "procesos": ["ansible", "nginx"]
    },
    {
        "name": "web2",
        "ip": "10.0.0.34",
        "user": "ansible",
        "password": "tu_clave",
        "procesos": ["docker", "haproxy"]
    }
]

def ejecutar_comando(vm, comando):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(vm["ip"], username=vm["user"], password=vm["password"], timeout=3)
        stdin, stdout, stderr = ssh.exec_command(comando)
        salida = stdout.read().decode()
        ssh.close()
        return salida
    except:
        return None

def get_vm_info(vm):
    try:
        uptime_output = ejecutar_comando(vm, "uptime")
        free_output = ejecutar_comando(vm, "free -m")
        disk_output = ejecutar_comando(vm, "df -h /")
        net_output = ejecutar_comando(vm, "ifstat -i ens18 1 1")

        cpu_load = uptime_output.split("load average:")[1].split(",")[0].strip()
        mem_line = free_output.splitlines()[1].split()
        mem_total = int(mem_line[1])
        mem_used = int(mem_line[2])
        mem_percent = round(mem_used / mem_total * 100, 2)
        disk_line = disk_output.splitlines()[1].split()
        disk_available = disk_line[3]

        net_lines = net_output.splitlines()
        if len(net_lines) > 2:
            net_received, net_sent = net_lines[2].split()
        else:
            net_received, net_sent = ('0', '0')

        # Verificar múltiples procesos
        estados_procesos = []
        for proc in vm.get("procesos", []):
            salida = ejecutar_comando(vm, f"ps aux | grep {proc} | grep -v grep")
            if salida and proc in salida:
                estados_procesos.append(f"✅ {proc}")
            else:
                estados_procesos.append(f"❌ {proc}")

        return {
            "status": "✅ OK",
            "cpu_load": cpu_load,
            "mem_percent": f"{mem_percent}%",
            "disk_available": disk_available,
            "net_received": net_received,
            "net_sent": net_sent,
            "uptime": uptime_output,
            "procesos_activos": estados_procesos
        }
    except:
        return {
            "status": "❌ Caído",
            "cpu_load": "-", "mem_percent": "-", "disk_available": "-",
            "net_received": "-", "net_sent": "-", "uptime": "-",
            "procesos_activos": ["No disponible"]
        }

@app.route('/')
def home():
    results = []
    for vm in vms:
        info = get_vm_info(vm)
        results.append({**vm, **info})
    return render_template("layout.html", vms=results)

@app.route('/accion/<nombre>/<tipo>')
def accion(nombre, tipo):
    for vm in vms:
        if vm["name"] == nombre:
            if tipo == "apagar":
                ejecutar_comando(vm, "systemctl poweroff -i")
            elif tipo == "reiniciar":
                ejecutar_comando(vm, "reboot")
    return redirect('/')

@app.route('/procesos/<nombre>')
def procesos(nombre):
    for vm in vms:
        if vm["name"] == nombre:
            salida = ejecutar_comando(vm, "ps aux | head -n 20")
            return f"<pre>{salida}</pre><a href='/'>⬅️ Volver</a>"
    return "VM no encontrada"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
