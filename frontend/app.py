"""
Frontend Flask application for RAG Chatbot
"""
from flask import Flask, render_template, request, jsonify, session
import requests
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "rag-workshop-secret-key-2024")

# Configuration
BACKEND_API_URL = "http://localhost:8000"  # URL de votre backend FastAPI

@app.route('/')
def index():
    """Page d'accueil du chat"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_pdf():
    """Uploader un PDF vers le backend"""
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Le fichier doit être un PDF'}), 400
    
    try:
        # Envoyer le fichier au backend
        files = {'file': (file.filename, file.stream, 'application/pdf')}
        response = requests.post(
            f"{BACKEND_API_URL}/upload-pdf",
            files=files
        )
        
        if response.status_code == 200:
            data = response.json()
            # Stocker le doc_id dans la session
            session['doc_id'] = data['doc_id']
            session['filename'] = file.filename
            return jsonify({
                'success': True,
                'doc_id': data['doc_id'],
                'filename': file.filename,
                'message': data['message']
            })
        else:
            return jsonify({'error': response.json().get('detail', 'Erreur lors de l\'upload')}), 500
            
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Impossible de se connecter au serveur backend'}), 500
    except Exception as e:
        return jsonify({'error': f'Erreur: {str(e)}'}), 500

@app.route('/chat', methods=['POST'])
def chat():
    """Envoyer une question au chatbot"""
    if 'doc_id' not in session:
        return jsonify({'error': 'Veuillez d\'abord uploader un PDF'}), 400
    
    data = request.json
    question = data.get('question', '').strip()
    
    if not question:
        return jsonify({'error': 'La question ne peut pas être vide'}), 400
    
    try:
        payload = {
            "doc_id": session['doc_id'],
            "question": question,
            "history": data.get('history', [])
        }
        
        response = requests.post(
            f"{BACKEND_API_URL}/chat",
            json=payload,
            timeout=30  # Timeout de 30 secondes
        )
        
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                'success': True,
                'answer': data['answer'],
                'sources': data.get('sources', []),
                'timestamp': datetime.now().strftime('%H:%M:%S')
            })
        else:
            return jsonify({'error': response.json().get('detail', 'Erreur lors de la génération')}), 500
            
    except requests.exceptions.Timeout:
        return jsonify({'error': 'La requête a pris trop de temps. Veuillez réessayer.'}), 408
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Impossible de se connecter au serveur backend'}), 500
    except Exception as e:
        return jsonify({'error': f'Erreur: {str(e)}'}), 500

@app.route('/reset', methods=['POST'])
def reset_session():
    """Réinitialiser la session (nouveau document)"""
    session.clear()
    return jsonify({'success': True, 'message': 'Session réinitialisée'})

@app.route('/health')
def health_check():
    """Vérifier l'état du frontend et du backend"""
    try:
        # Vérifier le backend
        backend_response = requests.get(f"{BACKEND_API_URL}/health", timeout=5)
        backend_status = backend_response.status_code == 200
        
        return jsonify({
            'frontend': 'healthy',
            'backend': 'healthy' if backend_status else 'unreachable',
            'backend_url': BACKEND_API_URL,
            'timestamp': datetime.now().isoformat()
        })
    except:
        return jsonify({
            'frontend': 'healthy',
            'backend': 'unreachable',
            'backend_url': BACKEND_API_URL,
            'timestamp': datetime.now().isoformat()
        }), 503

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')