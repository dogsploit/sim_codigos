import asyncio
import websockets
import ssl
import json
import logging
import os
import sys
import subprocess
import threading
import time
from datetime import datetime
from collections import defaultdict

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tunnel_server.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('WSS_Tunnel')

class TunnelServer:
    def __init__(self, host='0.0.0.0', port=8765):
        self.host = host
        self.port = port
        self.clients = {}
        self.tunnels = defaultdict(dict)
        self.sessions = {}
        self.ssl_context = self.create_ssl_context()
        
    def create_ssl_context(self):
        """Cria contexto SSL para WSS"""
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        
        # Gerar certificado auto-assinado se não existir
        if not os.path.exists('server.crt') or not os.path.exists('server.key'):
            self.generate_self_signed_cert()
        
        ssl_context.load_cert_chain('server.crt', 'server.key')
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        return ssl_context
    
    def generate_self_signed_cert(self):
        """Gera certificado SSL auto-assinado"""
        try:
            subprocess.run([
                'openssl', 'req', '-x509', '-newkey', 'rsa:4096',
                '-keyout', 'server.key', '-out', 'server.crt',
                '-days', '365', '-nodes',
                '-subj', '/CN=localhost'
            ], check=True, capture_output=True)
            logger.info("Certificado SSL gerado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao gerar certificado: {e}")
            sys.exit(1)
    
    async def handle_client(self, websocket, path):
        """Gerencia conexão do cliente"""
        client_id = id(websocket)
        logger.info(f"Novo cliente conectado: {client_id}")
        
        try:
            async for message in websocket:
                data = json.loads(message)
                await self.process_message(client_id, websocket, data)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Cliente {client_id} desconectado")
        finally:
            if client_id in self.clients:
                del self.clients[client_id]
    
    async def process_message(self, client_id, websocket, data):
        """Processa mensagens do cliente"""
        msg_type = data.get('type')
        
        if msg_type == 'register_tunnel':
            tunnel_id = data.get('tunnel_id')
            self.tunnels[tunnel_id]['client'] = client_id
            self.tunnels[tunnel_id]['websocket'] = websocket
            self.tunnels[tunnel_id]['created_at'] = datetime.now()
            
            await websocket.send(json.dumps({
                'type': 'tunnel_registered',
                'tunnel_id': tunnel_id,
                'status': 'active'
            }))
            
            logger.info(f"Tunnel {tunnel_id} registrado para cliente {client_id}")
            
        elif msg_type == 'data_transfer':
            tunnel_id = data.get('tunnel_id')
            payload = data.get('payload')
            target = data.get('target')
            
            if tunnel_id in self.tunnels:
                # Encaminhar dados para o destino
                if target == 'claude_interface':
                    await self.forward_to_claude(client_id, payload)
                elif target == 'chrome_headless':
                    await self.forward_to_chrome(client_id, payload)
                    
        elif msg_type == 'session_clone':
            session_data = data.get('session')
            session_id = data.get('session_id')
            self.sessions[session_id] = {
                'data': session_data,
                'client': client_id,
                'timestamp': datetime.now()
            }
            
            await websocket.send(json.dumps({
                'type': 'session_cloned',
                'session_id': session_id,
                'status': 'success'
            }))
    
    async def forward_to_claude(self, client_id, payload):
        """Encaminha dados para interface Claude"""
        # Simula acesso à interface Claude via localhost
        try:
            # Aqui você implementaria a lógica de acesso ao Claude
            # Por enquanto, apenas registramos
            logger.info(f"Dados encaminhados para Claude: {payload[:100]}...")
        except Exception as e:
            logger.error(f"Erro ao encaminhar para Claude: {e}")
    
    async def forward_to_chrome(self, client_id, payload):
        """Encaminha dados para Chrome Headless"""
        try:
            logger.info(f"Dados encaminhados para Chrome: {payload[:100]}...")
        except Exception as e:
            logger.error(f"Erro ao encaminhar para Chrome: {e}")
    
    async def start_server(self):
        """Inicia o servidor WebSocket"""
        async with websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            ssl=self.ssl_context,
            ping_interval=20,
            ping_timeout=60
        ):
            logger.info(f"Servidor WSS rodando em wss://{self.host}:{self.port}")
            await asyncio.Future()  # Roda para sempre

if __name__ == '__main__':
    server = TunnelServer()
    try:
        asyncio.run(server.start_server())
    except KeyboardInterrupt:
        logger.info("Servidor encerrado pelo usuário")
