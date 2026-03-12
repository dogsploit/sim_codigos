#!/bin/bash
# Script de setup completo para Tunnel SRI
# Arquivo: setup_completo.sh

echo "🚀 Iniciando setup do Tunnel SRI..."

# Criar diretórios necessários
mkdir -p certs logs chrome-data scripts

# Gerar certificados SSL
echo "📜 Gerando certificados SSL..."
openssl req -x509 -newkey rsa:4096 -keyout certs/server.key -out certs/server.crt -days 365 -nodes -subj "/CN=localhost"

# Instalar dependências Python
echo "🐍 Instalando dependências Python..."
pip3 install websockets aiohttp requests websocket-client

# Instalar Chrome Headless (Ubuntu/Debian)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "🌐 Instalando Chrome Headless..."
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
    sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
    sudo apt-get update
    sudo apt-get install -y google-chrome-stable
fi

# Instalar Node.js e dependências (opcional)
echo "📦 Instalando Node.js para ferramentas adicionais..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Criar arquivo de configuração
cat > config.json << EOF
{
    "wss_server": {
        "host": "0.0.0.0",
        "port": 8765,
        "ssl_cert": "certs/server.crt",
        "ssl_key": "certs/server.key"
    },
    "chrome": {
        "debug_port": 9222,
        "headless": true,
        "user_data_dir": "chrome-data"
    },
    "tunnel": {
        "reconnect_interval": 5,
        "max_retries": 10,
        "ping_interval": 30
    },
    "claude": {
        "url": "https://claude.ai",
        "timeout": 30000,
        "retry_attempts": 3
    }
}
EOF

# Criar arquivo de serviço systemd (opcional)
cat > tunnel-sri.service << EOF
[Unit]
Description=Tunnel SRI Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=$(which python3) $(pwd)/tunnel_manager.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Setup completo!"
echo ""
echo "Para iniciar o sistema:"
echo "1. Inicie o servidor WSS: python3 servidor_wss_tunnel.py"
echo "2. Inicie o Chrome Headless: python3 chrome_headless_launcher.py"
echo "3. Inicie o Tunnel Manager: python3 tunnel_manager.py"
echo ""
echo "Ou use Docker Compose: docker-compose up -d"
echo ""
echo "Arquivos criados:"
ls -la
