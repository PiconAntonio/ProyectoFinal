from flask import Flask, render_template, request, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy
import paramiko
import socket
import os

app = Flask(__name__)
app.secret_key = 'clave_secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///usuarios.db'
db = SQLAlchemy(app)

# Modelo de usuario
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    clave = db.Column(db.String(100), nullable=False)

# Crear la base de datos si no existe
with app.app_context():
    db.create_all()
    # Crear usuario inicial si no existe
    if not Usuario.query.filter_by(nombre="admin").first():
        nuevo = Usuario(nombre="admin", clave="1234")
        db.session.add(nuevo)
        db.session.commit()

# Lista de VMs a monitorear
vms = [
    {"name": "web1", "ip": "10.0.0.33", "user": "ansible", "password": "1", "proceso": "apache2"},
    {"name": "web2", "ip": "10.0.0.34", "user": "ansible", "password": "1", "proceso": "apache2"},
    {"name": "haproxy", "ip": "10.0.0.31", "user": "ansible", "password": "1", "proceso": "haproxy"},
    {"name": "ansible", "ip": "10.0.0.35", "user": "ansible", "password": "1", "proceso": "ansible"},
    {"name": "docker-node", "ip": "10.0.0.36", "user": "ansible", "password": "1", "proceso": "docker"},
    {"name": "docker2", "ip": "10.0.0.37", "user": "ansible", "password": "1", "proceso": "docker"}
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
        uptime = ejecutar_comando(vm, "uptime")
        free = ejecutar_comando(vm, "free -m")
        disk = ejecutar_comando(vm, "df -h /")
        net = ejecutar_comando(vm, "ifstat -i ens18 1 1")
        proceso = ejecutar_comando(vm, "ps -eo comm | sort | uniq -c | sort -nr | head -n 1")

        cpu_load = uptime.split("load average:")[1].split(",")[0].strip()

        mem_line = free.splitlines()[1].split()
        mem_total = int(mem_line[1])
        mem_used = int(mem_line[2])
        mem_percent = round(mem_used / mem_total * 100, 2)

        disk_line = disk.splitlines()[1].split()
        disk_available = disk_line[3]

        net_lines = net.splitlines()
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
            "uptime": uptime,
            "proceso": proceso.strip()
        }
    except:
        return {
            "status": "❌ Caído",
            "cpu_load": "-", "mem_percent": "-", "disk_available": "-",
            "net_received": "-", "net_sent": "-", "uptime": "-", "proceso": "-"
        }

@app.route('/')
def home():
    if "usuario" not in session:
        return redirect(url_for('login'))
    resultados = []
    for vm in vms:
        info = get_vm_info(vm)
        resultados.append({**vm, **info})
    return render_template("layout.html", vms=resultados, usuario=session["usuario"])

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nombre = request.form["usuario"]
        clave = request.form["clave"]
        usuario = Usuario.query.filter_by(nombre=nombre, clave=clave).first()
        if usuario:
            session["usuario"] = nombre
            return redirect('/')
        else:
            return "⚠️ Usuario o contraseña incorrectos"
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.pop("usuario", None)
    return redirect("/login")

@app.route('/accion/<nombre>/<tipo>')
def accion(nombre, tipo):
    if "usuario" not in session:
        return redirect(url_for('login'))
    for vm in vms:
        if vm["name"] == nombre:
            if tipo == "apagar":
                ejecutar_comando(vm, "systemctl poweroff -i")
            elif tipo == "reiniciar":
                ejecutar_comando(vm, "reboot")
    return redirect('/')

@app.route('/procesos/<nombre>')
def procesos(nombre):
    if "usuario" not in session:
        return redirect(url_for('login'))
    for vm in vms:
        if vm["name"] == nombre:
            salida = ejecutar_comando(vm, "ps aux | head -n 20")
            return f"<pre>{salida}</pre><a href='/'>⬅️ Volver</a>"
    return "VM no encontrada"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
