# config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'SUA_CHAVE_SECRETA_MUITO_FORTE' # Altere para uma chave secreta mais robusta em produção
    DEBUG = True # Mude para False em produção
    APP_ID = os.environ.get('FIREBASE_APP_ID', 'construcao-terceirizacao-app') # ID do seu projeto Firebase, atualizado para o novo tema
