# 🖥️ SmartMonitor 3.5" HID - Linux System Monitor

[![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)](https://github.com/joaogabrielmedeiros/SmartMonitor-3.5pol-HID)
[![Python](https://img.shields.io/badge/Python-3.9+-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)](https://github.com/joaogabrielmedeiros/SmartMonitor-3.5pol-HID)
[![Licence](https://img.shields.io/github/license/mathoudebine/turing-smart-screen-python?style=for-the-badge)](./LICENSE)

Este projeto é um **fork especializado** do repositório original [mathoudebine/turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python), desenvolvido com o objetivo principal de adicionar **suporte nativo e completo no Linux** para as telas secundárias USB de 3.5" baseadas em HID (especificamente o modelo **ID `0483:0065` STMicroelectronics / llTechCo.,Ltd**, comumente gerenciadas pelo software proprietário `SmartMonitor.exe` no Windows).

> [!IMPORTANT]
> **Compatibilidade Alcançada:** Este modelo de tela era anteriormente listado na comunidade como "não suportado no Linux". Com este fork, a tela agora inicializa, faz upload de temas compilados via YMODEM e renderiza monitoramento de hardware em tempo real diretamente em qualquer distribuição Linux (incluindo Fedora, Ubuntu, Debian e Raspberry Pi OS).

---

## 🚀 O que este Fork resolve:

* 🔌 **Driver HIDraw Nativo para Linux**: Suporte ao envio de comandos através de relatórios HID de 64 bytes para o dispositivo `/dev/hidraw*` sem depender de emulação de porta COM clássica.
* 🎨 **Upload de Skins Compiladas (`.dat`)**: Implementação do protocolo YMODEM sob conexão HIDraw com controle de atraso de 2ms entre pacotes para evitar buffer overflow no microcontrolador da tela.
* 📊 **Mapeamento Dinâmico de Sensores**: Vinculação das tags HID de skins proprietárias aos dados de monitoramento do sistema através de templates `.ui` (incluídos na pasta `vendor/`).
* 🏎️ **Correção das Métricas de GPU**: Inicialização correta da API de detecção do GPUtil no fluxo de runtime do SmartMonitor, resolvendo os campos em branco de GPU.
* 🎛️ **Configurador Refatorado (`configure.py`)**: O assistente gráfico Tkinter agora detecta chaves HIDraw automaticamente, permite mapear sensores individualmente para cada skin e possui integração real no botão "Save + run" para reiniciar o monitor de forma transparente.

---

## 🛠️ Como Configurar e Iniciar no Linux

### 1. Configurar Permissões USB (Udev Rules)
Para poder ler e gravar no dispositivo USB sem precisar rodar como `sudo`, crie uma regra do udev:

1. Crie o arquivo `/etc/udev/rules.d/99-smartmonitor-hiddev.rules`:
   ```text
   SUBSYSTEM=="hidraw", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="0065", MODE="0666", GROUP="plugdev"
   ```
2. Recarregue as regras:
   ```bash
   sudo udevadm control --reload-rules && sudo udevadm trigger
   ```
3. Reconecte o cabo USB da sua tela.

### 2. Configurar o Ambiente Python
Prepare o ambiente virtual e instale as dependências:
```bash
# Crie e ative o ambiente virtual
python3 -m venv venv
source venv/bin/activate

# Instale os pacotes necessários
pip install -r requirements.txt
```

### 3. Rodar o Assistente de Configuração
Abra a interface de configuração para selecionar seu modelo de tela e tema:
```bash
./venv/bin/python configure.py
```
* Em **Model**, selecione **SmartMonitor HID (experimental)**.
* Em **Size**, defina como **3.5"**.
* Escolha um tema compilado `.dat` disponível (como `rog03-vendor`).
* Clique em **Save + run**. O configurador salvará os dados e iniciará o serviço de monitoramento no terminal automaticamente!

### 4. Executar Diretamente via Terminal
Para rodar o monitor de hardware sem abrir a interface de configuração:
```bash
./venv/bin/python main.py
```

---

## 📁 Estrutura de Arquivos Adicionados/Modificados

* [library/lcd/lcd_comm_rev_a_hid.py](file:///home/jgm/playground/gemini/turing-smart-screen-python-main/library/lcd/lcd_comm_rev_a_hid.py): Implementa a escrita e leitura no dispositivo HIDraw, protocolo YMODEM com atraso entre pacotes e pacotes de comandos específicos do SmartMonitor.
* [library/smartmonitor_runtime.py](file:///home/jgm/playground/gemini/turing-smart-screen-python-main/library/smartmonitor_runtime.py): Serviço de plano de fundo que faz o polling dos sensores do sistema e envia as tags associadas à tela. Adicionada a detecção correta de GPUs.
* [library/display.py](file:///home/jgm/playground/gemini/turing-smart-screen-python-main/library/display.py): Abstração do display modificada para delegar a inicialização ao runtime HID ao invés de enviar comandos pixel-a-pixel.
* [configure.py](file:///home/jgm/playground/gemini/turing-smart-screen-python-main/configure.py): Assistente visual ajustado para gerenciar mapeamento de sensores, uploads imediatos e relançamento do monitor com `os.execv`.
* `vendor/`: Diretório adicionado contendo os arquivos originais `.ui` das skins de fábrica, essenciais para fazer o mapeamento correto de sensores.

---

## ❤️ Créditos e Licença

Este projeto é baseado no trabalho incrível do projeto original [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) sob licença **GPL-3.0**. 

Agradecimento especial a todos os contribuidores do repositório base que criaram a robusta arquitetura de sensores integrada a este fork!
