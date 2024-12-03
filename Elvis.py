import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
import sqlite3
import random
import string
import wikipedia
import subprocess
from datetime import datetime

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Conectar ao banco de dados SQLite
conn = sqlite3.connect('bot_database.db', check_same_thread=False)
cursor = conn.cursor()

# Criar tabelas necessárias
cursor.execute('''
CREATE TABLE IF NOT EXISTS notes
(user_id INTEGER, note TEXT)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS user_stats
(user_id INTEGER PRIMARY KEY, messages_sent INTEGER, first_use TIMESTAMP, last_use TIMESTAMP)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS bot_stats
(start_time TIMESTAMP, total_users INTEGER, total_messages INTEGER)
''')

conn.commit()

# Variáveis globais
BOT_ADMIN_ID = 6870644494  # Substitua pelo ID do administrador do bot
bot_start_time = datetime.now()

# Função para criar o menu principal
def main_menu():
    keyboard = [
        [KeyboardButton('Dicionário'), KeyboardButton('Gerador de Senhas')],
        [KeyboardButton('Notas Pessoais'), KeyboardButton('Verificar Ping')],
        [KeyboardButton('Conversar'), KeyboardButton('Wikipedia')],
        [KeyboardButton('Estatísticas')]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Funções de estatísticas
def update_user_stats(user_id):
    now = datetime.now()
    cursor.execute('''
    INSERT OR REPLACE INTO user_stats (user_id, messages_sent, first_use, last_use)
    VALUES (?, 
            COALESCE((SELECT messages_sent FROM user_stats WHERE user_id = ?) + 1, 1),
            COALESCE((SELECT first_use FROM user_stats WHERE user_id = ?), ?),
            ?)
    ''', (user_id, user_id, user_id, now, now))
    conn.commit()

def update_bot_stats():
    cursor.execute('''
    INSERT OR REPLACE INTO bot_stats (start_time, total_users, total_messages)
    VALUES (?, 
            (SELECT COUNT(DISTINCT user_id) FROM user_stats),
            (SELECT SUM(messages_sent) FROM user_stats))
    ''', (bot_start_time,))
    conn.commit()

async def show_user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT messages_sent, first_use, last_use FROM user_stats WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if result:
        messages_sent, first_use, last_use = result
        first_use = datetime.fromisoformat(first_use)
        last_use = datetime.fromisoformat(last_use)
        duration = last_use - first_use
        
        stats_message = (
            f"Suas estatísticas:\n"
            f"Mensagens enviadas: {messages_sent}\n"
            f"Primeiro uso: {first_use.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Último uso: {last_use.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Tempo total de uso: {duration}"
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(stats_message)
        else:
            await update.message.reply_text(stats_message, reply_markup=main_menu())
    else:
        message = "Nenhuma estatística disponível."
        if update.callback_query:
            await update.callback_query.edit_message_text(message)
        else:
            await update.message.reply_text(message, reply_markup=main_menu())

async def show_bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT total_users, total_messages FROM bot_stats")
    result = cursor.fetchone()
    
    if result:
        total_users, total_messages = result
        uptime = datetime.now() - bot_start_time
        
        stats_message = (
            f"Estatísticas do bot:\n"
            f"Total de usuários: {total_users}\n"
            f"Total de mensagens: {total_messages}\n"
            f"Tempo de atividade: {uptime}"
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(stats_message)
        else:
            await update.message.reply_text(stats_message, reply_markup=main_menu())
    else:
        message = "Nenhuma estatística disponível."
        if update.callback_query:
            await update.callback_query.edit_message_text(message)
        else:
            await update.message.reply_text(message, reply_markup=main_menu())

async def show_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != BOT_ADMIN_ID:
        message = "Acesso negado. Apenas o administrador pode ver essas estatísticas."
        if update.callback_query:
            await update.callback_query.edit_message_text(message)
        else:
            await update.message.reply_text(message, reply_markup=main_menu())
        return

    cursor.execute("SELECT SUM(messages_sent) FROM user_stats")
    total_messages = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user_stats")
    total_users = cursor.fetchone()[0] or 0

    uptime = datetime.now() - bot_start_time

    cursor.execute("SELECT user_id, messages_sent FROM user_stats ORDER BY messages_sent DESC LIMIT 5")
    top_users = cursor.fetchall()

    stats_message = (
        f"Estatísticas do administrador:\n"
        f"Total de usuários: {total_users}\n"
        f"Total de mensagens: {total_messages}\n"
        f"Tempo de atividade do bot: {uptime}\n\n"
        f"Top 5 usuários mais ativos:\n"
    )

    for user_id, messages in top_users:
        stats_message += f"Usuário {user_id}: {messages} mensagens\n"

    if update.callback_query:
        await update.callback_query.edit_message_text(stats_message)
    else:
        await update.message.reply_text(stats_message, reply_markup=main_menu())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bem-vindo! Escolha uma opção:", reply_markup=main_menu())
    context.user_data.clear()
    update_user_stats(update.effective_user.id)
    update_bot_stats()

async def off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot desativado. Use /start para reiniciar.")
    context.user_data.clear()  # Limpa o contexto

async def show_stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Minhas Estatísticas", callback_data='user_stats')],
        [InlineKeyboardButton("Estatísticas do Bot", callback_data='bot_stats')],
        [InlineKeyboardButton("Estatísticas do Admin", callback_data='admin_stats')],
        [InlineKeyboardButton("Voltar", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Escolha uma opção de estatísticas:", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'user_stats':
        await show_user_stats(update, context)
    elif query.data == 'bot_stats':
        await show_bot_stats(update, context)
    elif query.data == 'admin_stats':
        await show_admin_stats(update, context)
    elif query.data == 'back':
        await query.edit_message_text("Voltando ao menu principal:", reply_markup=main_menu())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_user_stats(update.effective_user.id)
    update_bot_stats()
    
    state = context.user_data.get('state', '')
    
    if state == 'expecting_word':
        await handle_dictionary(update, context)
    elif state == 'expecting_note':
        await save_note(update, context)
    elif state == 'expecting_address':
        await ping_address(update, context)
    elif state == 'expecting_wiki':
        await search_wikipedia(update, context)
    elif state == 'chatting':
        await respond_to_chat(update, context)
    else:
        text = update.message.text
        if text == 'Dicionário':
            await dictionary(update, context)
        elif text == 'Gerador de Senhas':
            await password_generator(update, context)
        elif text == 'Notas Pessoais':
            await personal_notes(update, context)
        elif text == 'Adicionar Nota':
            await add_note(update, context)
        elif text == 'Ver Notas':
            await view_notes(update, context)
        elif text == 'Limpar Notas':
            await clear_notes(update, context)
        elif text == 'Verificar Ping':
            await check_ping(update, context)
        elif text == 'Conversar':
            await chat(update, context)
        elif text == 'Wikipedia':
            await wikipedia_search(update, context)
        elif text == 'Estatísticas':
            await show_stats_menu(update, context)
        elif text == 'Voltar':
            await update.message.reply_text("Voltando ao menu principal:", reply_markup=main_menu())
            context.user_data.clear()
        else:
            await update.message.reply_text("Comando não reconhecido. Por favor, use o menu.", reply_markup=main_menu())

# Adicione aqui as outras funções (dictionary, password_generator, personal_notes, etc.) que não foram modificadas
async def dictionary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Digite a palavra que deseja buscar no dicionário:")
    context.user_data['state'] = 'expecting_word'

async def handle_dictionary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    word = update.message.text
    # Implemente aqui a lógica real de busca no dicionário
    definition = f"Definição de {word}: [Implementar busca em API de dicionário]"
    await update.message.reply_text(definition, reply_markup=main_menu())
    context.user_data.clear()

async def password_generator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = ''.join(random.choice(string.ascii_letters + string.digits + string.punctuation) for _ in range(12))
    await update.message.reply_text(f"Sua senha gerada: {password}", reply_markup=main_menu())

async def personal_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton('Adicionar Nota'), KeyboardButton('Ver Notas')],
        [KeyboardButton('Limpar Notas'), KeyboardButton('Voltar')]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Escolha uma opção:", reply_markup=reply_markup)

async def add_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Digite sua nota (máximo 500 caracteres):")
    context.user_data['state'] = 'expecting_note'

async def save_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    note = update.message.text
    if len(note) > 500:
        await update.message.reply_text("A nota é muito longa. Por favor, limite-a a 500 caracteres.", reply_markup=main_menu())
    else:
        cursor.execute("INSERT INTO notes (user_id, note) VALUES (?, ?)", (user_id, note))
        conn.commit()
        await update.message.reply_text("Nota salva com sucesso!", reply_markup=main_menu())
    context.user_data.clear()

async def view_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("SELECT note FROM notes WHERE user_id = ?", (user_id,))
    notes = cursor.fetchall()
    if notes:
        note_list = "\n".join([note[0] for note in notes])
        await update.message.reply_text(f"Suas notas:\n{note_list}", reply_markup=main_menu())
    else:
        await update.message.reply_text("Você não tem notas salvas.", reply_markup=main_menu())

async def clear_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cursor.execute("DELETE FROM notes WHERE user_id = ?", (user_id,))
    conn.commit()
    await update.message.reply_text("Todas as suas notas foram apagadas.", reply_markup=main_menu())

async def check_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Digite o endereço para verificar o ping:")
    context.user_data['state'] = 'expecting_address'

async def ping_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    address = update.message.text
    try:
        result = subprocess.run(['ping', '-c', '4', address], capture_output=True, text=True)
        if result.returncode == 0:
            output = result.stdout.split('\n')[-2]
            await update.message.reply_text(f"Resultado do ping: {output}", reply_markup=main_menu())
        else:
            await update.message.reply_text(f"Não foi possível fazer ping para {address}", reply_markup=main_menu())
    except Exception as e:
        await update.message.reply_text(f"Erro ao verificar ping: {str(e)}", reply_markup=main_menu())
    context.user_data.clear()

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Olá! Sobre o que você gostaria de conversar?")
    context.user_data['state'] = 'chatting'

async def respond_to_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    words = text.split()
    response = f"Entendi que você falou sobre: {', '.join(words[:5])}. Quer falar mais sobre isso?"
    await update.message.reply_text(response)

async def wikipedia_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Digite o termo que deseja buscar na Wikipedia:")
    context.user_data['state'] = 'expecting_wiki'

async def search_wikipedia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    try:
        wikipedia.set_lang("pt")
        page = wikipedia.page(query)
        result = page.summary[:1000]  # Limita o resumo a 1000 caracteres
        await update.message.reply_text(result, reply_markup=main_menu())
    except wikipedia.exceptions.DisambiguationError as e:
        options = e.options[:5]
        await update.message.reply_text(f"Termo ambíguo. Opções: {', '.join(options)}\nPor favor, seja mais específico.", reply_markup=main_menu())
    except wikipedia.exceptions.PageError:
        await update.message.reply_text("Não foi possível encontrar informações sobre esse termo.", reply_markup=main_menu())
    except Exception as e:
        await update.message.reply_text(f"Ocorreu um erro ao buscar: {str(e)}", reply_markup=main_menu())
    context.user_data.clear()

def main():
    application = ApplicationBuilder().token('').build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("off", off))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Adicionar handler para callbacks dos botões inline
    application.add_handler(CallbackQueryHandler(button))
    
    application.run_polling()

if __name__ == '__main__':
    main()
