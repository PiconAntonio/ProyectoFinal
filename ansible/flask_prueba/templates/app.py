from flask import Flask, render_template, request, redirect, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_sqlalchemy import SQLAlchemy
import paramiko
import socket
import os
import datetime

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = 'clave_secreta'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:root@localhost/monitoring_db'
db = SQLAlchemy(app)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    clave = db.Column(db.String(100), nullable=False)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    usuario = db.relationship('Usuario', backref=db.backref('logs', lazy=True))
    mensaje = db.Column(db.String(255), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class ReglaRed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    accion = db.Column(db.String(50), nullable=False)
    protocolo = db.Column(db.String(20), nullable=False)
    puerto = db.Column(db.Integer, nullable=False)
    origen_ip = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.String(255), nullable=False)

with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(nombre="admin").first():
        nuevo = Usuario(nombre="admin", clave="1234")
        db.session.add(nuevo)
        db.session.commit()

vms = [
    {"name": "web1", "ip": "10.0.0.33", "user": "ansible", "password": "1", "procesos": ["apache2"]},
    {"name": "web2", "ip": "10.0.0.34", "user": "ansible", "password": "1", "procesos": ["apache2"]},
    {"name": "haproxy", "ip": "10.0.0.31", "user": "ansible", "password": "1", "procesos": ["haproxy", "keepalived"]},
    {"name": "ansible", "ip": "10.0.0.35", "user": "ansible", "password": "1", "procesos": ["ansible"]},
    {"name": "docker-node", "ip": "10.0.0.36", "user": "ansible", "password": "1", "procesos": ["docker", "keepalived"]},
    {"name": "docker2", "ip": "10.0.0.37", "user": "ansible", "password": "1", "procesos": ["docker"]}
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

        procesos_estado = {}
        for proc in vm.get("procesos", []):
            salida = ejecutar_comando(vm, f"pgrep -x {proc}")
            procesos_estado[proc] = "✅" if salida else "❌"

        return {
            "status": "✅ OK",
            "cpu_load": cpu_load,
            "mem_percent": f"{mem_percent}%",
            "disk_available": disk_available,
            "net_received": net_received,
            "net_sent": net_sent,
            "uptime": uptime,
            "procesos": procesos_estado
        }
    except:
        return {
            "status": "❌ Caído",
            "cpu_load": "-", "mem_percent": "-", "disk_available": "-",
            "net_received": "-", "net_sent": "-", "uptime": "-", "procesos": {}
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
            log = Log(usuario_id=usuario.id, mensaje="Login exitoso")
            db.session.add(log)
            db.session.commit()
            return redirect('/')
        else:
            return "⚠️ Usuario o contraseña incorrectos"
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.pop("usuario", None)
    return redirect("/login")

@app.route('/reglas', methods=["GET", "POST"])
def reglas():
    if "usuario" not in session:
        return redirect(url_for('login'))
    if request.method == "POST":
        accion = request.form["accion"]
        protocolo = request.form["protocolo"]
        puerto = request.form["puerto"]
        origen_ip = request.form["origen_ip"]
        descripcion = request.form["descripcion"]
        nueva_regla = ReglaRed(accion=accion, protocolo=protocolo, puerto=puerto, origen_ip=origen_ip, descripcion=descripcion)
        db.session.add(nueva_regla)
        db.session.commit()
        return redirect('/reglas')
    reglas = ReglaRed.query.all()
    return render_template("reglas.html", reglas=reglas)

@app.route('/logs')
def ver_logs():
    if "usuario" not in session:
        return redirect(url_for('login'))
    logs = Log.query.all()
    return render_template("logs.html", logs=logs)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

