from flask import Flask, render_template, redirect
import paramiko

app = Flask(__name__)

# Lista de tus máquinas
vms = [
    {"nombre": "Servidor 1", "ip": "192.168.1.101", "usuario": "usuario", "clave": "clave"},
    {"nombre": "Servidor 2", "ip": "192.168.1.102", "usuario": "usuario", "clave": "clave"},
]

# Función para conectarse y ejecutar comando
def ejecutar(ip, usuario, clave, comando):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=usuario, password=clave)
        stdin, stdout, stderr = ssh.exec_command(comando)
        resultado = stdout.read().decode()
        ssh.close()
        return resultado
    except:
        return "Error"

# Ruta principal que muestra todo
@app.route('/')
def index():
    datos = []
    for vm in vms:
        cpu = ejecutar(vm["ip"], vm["usuario"], vm["clave"], "top -bn1 | grep '%Cpu' | awk '{print $2}'").strip()
        mem = ejecutar(vm["ip"], vm["usuario"], vm["clave"], "free | grep Mem").split()
        disco = ejecutar(vm["ip"], vm["usuario"], vm["clave"], "df -h / | tail -1 | awk '{print $5}'").strip()
        procesos = ejecutar(vm["ip"], vm["usuario"], vm["clave"], "ps -e | wc -l").strip()

        if len(mem) >= 3:
            mem_usada = round((int(mem[2]) / int(mem[1])) * 100, 2)
        else:
            mem_usada = "?"

        datos.append({
            "nombre": vm["nombre"],
            "cpu": cpu,
            "mem": mem_usada,
            "disco": disco,
            "procesos": procesos
        })
    return render_template("index.html", vms=datos)

# Ruta para apagar o reiniciar
@app.route('/accion/<nombre>/<tipo>')
def accion(nombre, tipo):
    for vm in vms:
        if vm["nombre"] == nombre:
            if tipo == "apagar":
                ejecutar(vm["ip"], vm["usuario"], vm["clave"], "shutdown now")
            elif tipo == "reiniciar":
                ejecutar(vm["ip"], vm["usuario"], vm["clave"], "reboot")
    return redirect('/')

# Ruta para ver procesos
@app.route('/procesos/<nombre>')
def procesos(nombre):
    for vm in vms:
        if vm["nombre"] == nombre:
            salida = ejecutar(vm["ip"], vm["usuario"], vm["clave"], "ps aux | head -n 20")
            return f"<pre>{salida}</pre><a href='/'>⬅️ Volver</a>"
    return "VM no encontrada"
