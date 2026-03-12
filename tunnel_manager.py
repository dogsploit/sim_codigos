#!/usr/bin/env python3
"""
Gerenciador de Tunnel SRI
Arquivo: tunnel_manager.py
"""

import asyncio
import websockets
import json
import base64
import ssl
import os
import sys
import time
import subprocess
import threading
from pathlib import Path

class TunnelManager:
    def __init__(self, wss_url='wss://localhost:8765'):
        self.wss_url = wss_url
        self.websocket = None
        self.tunnel_id = None
        self.running = True
        self.chrome_process = None
        self.ssl_context = self.create_ssl_context()
        
    def create_ssl_context(self):
        """Cria contexto SSL ignorando verificação"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context
    
    async def connect(self):
        """Conecta ao servidor WSS"""
        try:
            self.websocket = await websockets.connect(
                self.wss_url,
                ssl=self.ssl_context,
                ping_interval=20,
                ping_timeout=60
            )
            
            # Registrar tunnel
            self.tunnel_id = f"tunnel_{int(time.time())}_{os.getpid()}"
            await self.websocket.send(json.dumps({
                'type': 'register_tunnel',
                'tunnel_id': self.tunnel_id,
                'client': 'python_manager'
            }))
            
            response = await self.websocket.recv()
            data = json.loads(response)
            
            if data.get('type') == 'tunnel_registered':
                print(f"Tunnel {self.tunnel_id} registrado com sucesso")
                return True
                
        except Exception as e:
            print(f"Erro ao conectar: {e}")
            return False
    
    async def send_data(self, data, target='claude_interface', encoding=None):
        """Envia dados através do tunnel"""
        if not self.websocket:
            print("WebSocket não conectado")
            return False
            
        message = {
            'type': 'data_transfer',
            'tunnel_id': self.tunnel_id,
            'target': target,
            'payload': data,
            'timestamp': time.time()
        }
        
        if encoding == 'base64':
            # Codificar payload em Base64
            if isinstance(data, str):
                message['payload'] = base64.b64encode(data.encode()).decode()
            elif isinstance(data, bytes):
                message['payload'] = base64.b64encode(data).decode()
            message['encoding'] = 'base64'
        
        try:
            await self.websocket.send(json.dumps(message))
            return True
        except Exception as e:
            print(f"Erro ao enviar dados: {e}")
            return False
    
    async def receive_loop(self):
        """Loop de recebimento de mensagens"""
        while self.running:
            try:
                message = await self.websocket.recv()
                data = json.loads(message)
                
                # Processar mensagens recebidas
                if data.get('type') == 'data_transfer':
                    payload = data.get('payload')
                    encoding = data.get('encoding')
                    
                    if encoding == 'base64':
                        payload = base64.b64decode(payload).decode()
                    
                    print(f"Dados recebidos: {payload[:100]}...")
                    
                    # Encaminhar para o destino apropriado
                    await self.route_data(payload, data.get('target'))
                    
                elif data.get('type') == 'ping':
                    await self.websocket.send(json.dumps({
                        'type': 'pong',
                        'tunnel_id': self.tunnel_id,
                        'time': time.time()
                    }))
                    
            except websockets.exceptions.ConnectionClosed:
                print("Conexão fechada. Tentando reconectar...")
                await self.reconnect()
                break
            except Exception as e:
                print(f"Erro no receive loop: {e}")
    
    async def route_data(self, data, target):
        """Roteia dados para o destino correto"""
        if target == 'chrome_headless':
            # Enviar comando para Chrome
            await self.send_to_chrome(data)
        elif target == 'python_runtime':
            # Executar no Python local
            await self.execute_python(data)
    
    async def send_to_chrome(self, command):
        """Envia comando para Chrome Headless via DevTools"""
        try:
            # Conectar ao DevTools do Chrome
            import requests
            
            # Obter URL do debugger
            response = requests.get('http://localhost:9222/json/version')
            if response.status_code == 200:
                debugger_url = response.json().get('webSocketDebuggerUrl')
                
                if debugger_url:
                    # Conectar via WebSocket
                    import websocket
                    
                    ws = websocket.WebSocket()
                    ws.connect(debugger_url.replace('ws://', 'ws://localhost:'))
                    
                    # Executar JavaScript
                    ws.send(json.dumps({
                        'id': 1,
                        'method': 'Runtime.evaluate',
                        'params': {
                            'expression': f'window.tunnelAPI?.sendData({json.dumps(command)})'
                        }
                    }))
                    
                    ws.close()
                    
        except Exception as e:
            print(f"Erro ao enviar para Chrome: {e}")
    
    async def execute_python(self, code):
        """Executa código Python localmente"""
        try:
            # Criar ambiente de execução seguro
            exec_globals = {
                '__builtins__': __builtins__,
                'print': print,
                'json': json,
                'base64': base64
            }
            
            # Executar código
            exec(code, exec_globals)
            
        except Exception as e:
            print(f"Erro executando Python: {e}")
    
    async def reconnect(self):
        """Reconecta ao servidor"""
        retry_count = 0
        while self.running and retry_count < 10:
            try:
                if await self.connect():
                    print("Reconectado com sucesso")
                    asyncio.create_task(self.receive_loop())
                    break
            except:
                retry_count += 1
                wait_time = min(30, 2 ** retry_count)
                print(f"Tentativa {retry_count} falhou. Tentando novamente em {wait_time}s")
                await asyncio.sleep(wait_time)
    
    async def run(self):
        """Executa o gerenciador"""
        if await self.connect():
            # Iniciar receive loop
            receive_task = asyncio.create_task(self.receive_loop())
            
            # Loop principal
            try:
                while self.running:
                    # Manter conexão ativa
                    await asyncio.sleep(1)
                    
            except KeyboardInterrupt:
                print("\nEncerrando...")
                self.running = False
            
            # Aguardar tasks
            receive_task.cancel()
            try:
                await receive_task
            except:
                pass
    
    def start_chrome_headless(self):
        """Inicia Chrome Headless em processo separado"""
        chrome_path = '/usr/bin/google-chrome'
        if not os.path.exists(chrome_path):
            chrome_path = '/usr/bin/chromium-browser'
            
        chrome_args = [
            chrome_path,
            '--headless',
            '--disable-gpu',
            '--no-sandbox',
            '--remote-debugging-port=9222',
            '--disable-web-security',
            '--ignore-certificate-errors',
            '--user-data-dir=/tmp/chrome_data',
            '--enable-features=NetworkService,NetworkServiceInProcess',
            '--disable-blink-features=AutomationControlled',
            '--window-size=1920,1080',
            '--enable-logging=stderr',
            '--v=1',
            f'--user-agent=Mozilla/5.0 TunnelBot/{self.tunnel_id}',
            'https://claude.ai'  # URL alvo
        ]
        
        self.chrome_process = subprocess.Popen(
            chrome_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        print(f"Chrome Headless iniciado com PID: {self.chrome_process.pid}")
        return self.chrome_process

def main():
    """Função principal"""
    manager = TunnelManager()
    
    # Iniciar Chrome Headless em thread separada
    import threading
    chrome_thread = threading.Thread(target=manager.start_chrome_headless)
    chrome_thread.daemon = True
    chrome_thread.start()
    
    # Aguardar Chrome iniciar
    time.sleep(3)
    
    # Executar manager
    asyncio.run(manager.run())

if __name__ == '__main__':
    main()
