#!/usr/bin/env bash
pip install -r requirements.txt
python -c "import app; app.inicializar_banco()"