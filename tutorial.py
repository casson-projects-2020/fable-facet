from flask import Flask, render_template_string, request, redirect
import subprocess
import json

app = Flask(__name__)

def get_projects():
    # Busca a lista de projetos que o usuário tem acesso
    result = subprocess.run(
        ['gcloud', 'projects', 'list', '--format=json'],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Fable Facet - Seletor de Projeto</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f8f9fa; display: flex; justify-content: center; padding: 50px; }
        .container { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%; max-width: 500px; }
        h2 { color: #1a73e8; margin-top: 0; }
        select { width: 100%; padding: 12px; margin: 20px 0; border: 2px solid #ddd; border-radius: 8px; font-size: 16px; }
        button { background: #1a73e8; color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: bold; width: 100%; }
        button:hover { background: #1557b0; }
        .status { margin-top: 20px; color: #555; font-size: 14px; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Selecione seu Projeto</h2>
        <p>Não encontramos um projeto configurado. Escolha um na lista abaixo para continuar:</p>
        
        <form action="/set-project" method="post">
            <select name="project_id">
                {% for p in projects %}
                <option value="{{ p.projectId }}">{{ p.name }} ({{ p.projectId }})</option>
                {% endfor %}
            </select>
            <button type="submit">Confirmar e Configurar</button>
        </form>
        
        {% if msg %}
        <div class="status">✅ {{ msg }}</div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    projects = get_projects()
    return render_template_string(HTML_TEMPLATE, projects=projects)

@app.route('/set-project', method=['POST'])
def set_project():
    project_id = request.form.get('project_id')
    # Executa o comando de configuração no terminal do Cloud Shell
    subprocess.run(['gcloud', 'config', 'set', 'project', project_id])
    
    # Aqui você pode redirecionar para o próximo passo do seu tutorial personalizado
    return render_template_string(HTML_TEMPLATE, projects=get_projects(), msg=f"Projeto {project_id} configurado com sucesso!")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
