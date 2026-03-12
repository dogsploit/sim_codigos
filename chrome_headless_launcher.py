#!/usr/bin/env python3
"""
Lançador do Chrome Headless com Pyodide
Arquivo: chrome_headless_launcher.py
"""

import subprocess
import os
import sys
import time
import json
import socket
import requests
from pathlib import Path

class ChromeHeadlessLauncher:
    def __init__(self, wss_url='wss://localhost:8765', chrome_path=None):
        self.wss_url = wss_url
        self.chrome_path = chrome_path or self.find_chrome()
        self.debug_port = 9222
        self.process = None
        self.ws_client = None
        
    def find_chrome(self):
        """Encontra o executável do Chrome"""
        common_paths = [
            '/usr/bin/google-chrome',
            '/usr/bin/chromium-browser',
            '/usr/bin/chromium',
            'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
            'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
                
        # Se não encontrar, tenta comando 'which'
        try:
            result = subprocess.run(['which', 'google-chrome'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
            
        raise Exception("Chrome não encontrado. Instale o Google Chrome ou Chromium.")
    
    def launch_headless(self):
        """Inicia Chrome em modo headless com debugging"""
        chrome_args = [
            self.chrome_path,
            '--headless',
            '--disable-gpu',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--remote-debugging-port={}'.format(self.debug_port),
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--ignore-certificate-errors',
            '--disable-blink-features=AutomationControlled',
            '--user-data-dir=/tmp/chrome_headless_{}'.format(int(time.time())),
            '--window-size=1920,1080',
            '--disable-setuid-sandbox',
            '--disable-logging',
            '--log-level=3',
            '--silent',
            '--mute-audio',
            '--enable-webgl',
            '--enable-features=WebRTCPipeWireCapturer,WebRTC-H264WithH264',
            '--force-webrtc-ip-handling-policy=default_public_interface_only',
            '--webrtc-ip-handling-policy=disable_non_proxied_udp',
            '--enable-experimental-web-platform-features',
            '--enable-blink-features=WebRTC,WebSocket,WebTransport',
            '--enable-quic',
            '--quic-version=h3-29',
            '--origin-to-force-quic-on=localhost:8765',
            'about:blank'
        ]
        
        print(f"Iniciando Chrome Headless na porta {self.debug_port}")
        self.process = subprocess.Popen(chrome_args, 
                                       stdout=subprocess.DEVNULL, 
                                       stderr=subprocess.DEVNULL)
        
        # Aguarda Chrome iniciar
        time.sleep(3)
        
        # Verifica se está rodando
        if self.process.poll() is None:
            print("Chrome Headless iniciado com sucesso!")
            return True
        else:
            print("Falha ao iniciar Chrome Headless")
            return False
    
    def get_debugger_url(self):
        """Obtém URL do debugger do Chrome"""
        try:
            response = requests.get(f'http://localhost:{self.debug_port}/json/version')
            if response.status_code == 200:
                data = response.json()
                return data.get('webSocketDebuggerUrl')
        except:
            pass
        return None
    
    def inject_pyodide(self):
        """Injeta Pyodide no Chrome Headless via DevTools Protocol"""
        debugger_url = self.get_debugger_url()
        if not debugger_url:
            print("Não foi possível conectar ao debugger do Chrome")
            return False
            
        # Conecta via WebSocket ao debugger
        import websocket
        
        ws = websocket.WebSocket()
        ws.connect(debugger_url.replace('ws://', 'ws://localhost:'))
        
        # Habilita Runtime
        ws.send(json.dumps({
            'id': 1,
            'method': 'Runtime.enable'
        }))
        
        # Carrega Pyodide
        pyodide_script = """
        // Carregar Pyodide
        var script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/pyodide/v0.24.1/full/pyodide.js';
        script.onload = function() {
            console.log('Pyodide carregado!');
            window.loadPyodide({
                indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.24.1/full/',
                fullStdLib: false
            }).then((pyodide) => {
                window.pyodide = pyodide;
                console.log('Pyodide inicializado!');
            });
        };
        document.head.appendChild(script);
        """
        
        ws.send(json.dumps({
            'id': 2,
            'method': 'Runtime.evaluate',
            'params': {
                'expression': pyodide_script,
                'awaitPromise': True
            }
        }))
        
        ws.close()
        return True
    
    def run_forever(self):
        """Mantém o processo rodando"""
        try:
            while True:
                if self.process.poll() is not None:
                    print("Chrome Headless encerrou. Reiniciando...")
                    self.launch_headless()
                    self.inject_pyodide()
                time.sleep(5)
        except KeyboardInterrupt:
            print("\nEncerrando Chrome Headless...")
            self.process.terminate()
            self.process.wait()

if __name__ == '__main__':
    launcher = ChromeHeadlessLauncher()
    if launcher.launch_headless():
        launcher.inject_pyodide()
        launcher.run_forever()
