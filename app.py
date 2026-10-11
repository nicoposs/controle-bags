import os
import sqlite3
from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = "sua_chave_secreta_aqui"

SENHA_ADMIN = "admin123"


def inicializar_banco():
  conexao = sqlite3.connect("producao.db")
  cursor = conexao.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS bgas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL,
            molde TEXT NOT NULL,
            peso REAL NOT NULL,
            referencia TEXT NOT NULL,
            material TEXT DEFAULT 'PLA',
            data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
  # Garante compatibilidade se a tabela já existia sem a coluna material
  try:
    cursor.execute("ALTER TABLE bgas ADD COLUMN material TEXT DEFAULT 'PLA'")
  except sqlite3.OperationalError:
    pass  # A coluna já existe
  conexao.commit()
  conexao.close()


def conectar_banco():
  return sqlite3.connect("producao.db")


@app.route("/", methods=["GET", "POST"])
def index():
  conexao = conectar_banco()
  cursor = conexao.cursor()

  # Cadastro pelo site
  if request.method == "POST":
    codigo = request.form.get("codigo").strip()
    molde = request.form.get("molde").strip()
    peso_str = request.form.get("peso").strip().replace(",", ".")
    referencia = request.form.get("referencia").strip()
    material = request.form.get("material").strip()

    if codigo and molde and peso_str and referencia and material:
      try:
        peso = float(peso_str)
        cursor.execute(
            """
                    INSERT INTO bgas (codigo, molde, peso, referencia, material) 
                    VALUES (?, ?, ?, ?, ?)
                """,
            (codigo, molde, peso, referencia, material),
        )
        conexao.commit()
      except ValueError:
        pass
    conexao.close()
    return redirect(url_for("index"))

  # Estatísticas gerais (Máx, Méd, Mín)
  cursor.execute("""
        SELECT MAX(peso), AVG(peso), MIN(peso) FROM bgas
    """)
  estatisticas = cursor.fetchone()
  peso_max = round(estatisticas[0], 2) if estatisticas[0] else 0
  peso_med = round(estatisticas[1], 2) if estatisticas[1] else 0
  peso_min = round(estatisticas[2], 2) if estatisticas[2] else 0

  # Buscar meses e materiais disponíveis para os filtros
  cursor.execute("""
        SELECT DISTINCT strftime('%Y-%m', data_registro) as mes_ano 
        FROM bgas WHERE data_registro IS NOT NULL ORDER BY mes_ano DESC
    """)
  meses_disponiveis = [row[0] for row in cursor.fetchall()]

  cursor.execute(
      "SELECT DISTINCT material FROM bgas WHERE material IS NOT NULL ORDER BY"
      " material ASC"
  )
  materiais_disponiveis = [row[0] for row in cursor.fetchall()]

  # Capturar os filtros selecionados pelo usuário
  mes_selecionado = request.args.get("mes_filtro", "")
  material_selecionado = request.args.get("material_filtro", "")

  # Montar a consulta SQL com base nos filtros ativos
  query = """
        SELECT 
            strftime('%Y-%m', data_registro) as mes_ano,
            codigo,
            AVG(peso) as media_peso
        FROM bgas
        WHERE 1=1
    """
  params = []

  if mes_selecionado:
    query += " AND strftime('%Y-%m', data_registro) = ?"
    params.append(mes_selecionado)

  if material_selecionado:
    query += " AND material = ?"
    params.append(material_selecionado)

  query += " GROUP BY mes_ano, codigo ORDER BY mes_ano ASC"

  cursor.execute(query, params)
  dados_grafico = cursor.fetchall()

  meses = sorted(list(set(row[0] for row in dados_grafico)))
  codigos = sorted(list(set(row[1] for row in dados_grafico)))
  datasets = []

  cores = ["#dc2626", "#111827", "#4b5563", "#9ca3af", "#ef4444", "#000000"]

  for i, cod in enumerate(codigos):
    pesos_por_mes = []
    for mes in meses:
      encontrou = False
      for row in dados_grafico:
        if row[0] == mes and row[1] == cod:
          pesos_por_mes.append(round(row[2], 2))
          encontrou = True
          break
      if not encontrou:
        pesos_por_mes.append(None)

    datasets.append({
        "label": f"BAG: {cod}",
        "data": pesos_por_mes,
        "borderColor": cores[i % len(cores)],
        "backgroundColor": cores[i % len(cores)],
        "tension": 0.1,
    })

  # Histórico recente (incluindo o material)
  cursor.execute(
      "SELECT id, codigo, molde, peso, referencia, material, data_registro FROM"
      " bgas ORDER BY id DESC LIMIT 10"
  )
  historico = cursor.fetchall()

  conexao.close()
  is_admin = session.get("is_admin", False)

  return render_template(
      "index.html",
      peso_max=peso_max,
      peso_med=peso_med,
      peso_min=peso_min,
      meses=meses,
      datasets=datasets,
      historico=historico,
      is_admin=is_admin,
      meses_disponiveis=meses_disponiveis,
      materiais_disponiveis=materiais_disponiveis,
      mes_selecionado=mes_selecionado,
      material_selecionado=material_selecionado,
  )


@app.route("/login", methods=["POST"])
def login():
  senha = request.form.get("senha")
  if senha == SENHA_ADMIN:
    session["is_admin"] = True
  else:
    session["is_admin"] = False
  return redirect(url_for("index"))


@app.route("/logout")
def logout():
  session.pop("is_admin", None)
  return redirect(url_for("index"))


@app.route("/apagar/<int:id>", methods=["POST"])
def apagar(id):
  if not session.get("is_admin"):
    return redirect(url_for("index"))

  conexao = conectar_banco()
  cursor = conexao.cursor()
  cursor.execute("DELETE FROM bgas WHERE id = ?", (id,))
  conexao.commit()
  conexao.close()
  return redirect(url_for("index"))


if __name__ == "__main__":
  inicializar_banco()
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
